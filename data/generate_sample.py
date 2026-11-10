"""
SmartBus Benchmark Dataset Generator
Generates: 'Ticket data_1 Day_City Service.xlsx' with worksheet 'sql (12)'
Records: exactly 19,275 rows
Columns (10 immutable fields):
1. Waybill Number
2. Ticket Number
3. From Stop
4. To Stop
5. Date
6. Time
7. Total Psgr
8. Coll Amt
9. Uncoll Amt
10. Unnamed: 9
"""

import os
import random
import datetime
import pandas as pd
import numpy as np

def generate_sample_dataset(output_dir="data/sample", num_records=19275):
    os.makedirs(output_dir, exist_ok=True)
    excel_path = os.path.join(output_dir, "Ticket data_1 Day_City Service.xlsx")
    csv_path = os.path.join(output_dir, "Ticket data_1 Day_City Service.csv")

    random.seed(42)
    np.random.seed(42)

    # Karnataka City Service Major Stops
    major_stops = [
        "Kempegowda Bus Station",
        "Shivajinagar",
        "Banashankari TTMC",
        "Electronic City Gate 1",
        "Whitefield TTMC",
        "KR Puram Railway Station",
        "Central Silk Board",
        "Yeshwantpur TTMC",
        "Hebbal Junction",
        "Koramangala Bus Station",
        "Indiranagar 100ft Road",
        "Jayanagar 4th Block",
        "Kengeri TTMC",
        "BTM Layout 2nd Stage",
        "Vijayanagar TTMC",
        "Malleshwaram 8th Cross",
        "Yelahanka Old Town",
        "Domlur TTMC",
        "Marathahalli Bridge",
        "Shanthinagar Bus Station"
    ]

    # Generate ~65 active waybills
    waybills = [f"WB-{1000 + i}" for i in range(1, 66)]

    # Time distribution weights: morning peak (8-11), evening peak (17-20)
    hours = list(range(5, 24))
    hour_weights = [
        0.02, # 5 AM
        0.04, # 6 AM
        0.07, # 7 AM
        0.11, # 8 AM (Peak)
        0.12, # 9 AM (Peak)
        0.10, # 10 AM (Peak)
        0.06, # 11 AM
        0.05, # 12 PM
        0.04, # 1 PM
        0.04, # 2 PM
        0.05, # 3 PM
        0.06, # 4 PM
        0.10, # 5 PM (Peak)
        0.11, # 6 PM (Peak)
        0.09, # 7 PM (Peak)
        0.06, # 8 PM
        0.04, # 9 PM
        0.02, # 10 PM
        0.01  # 11 PM
    ]
    # Normalize weights
    hour_weights = [w / sum(hour_weights) for w in hour_weights]

    target_date = "2026-10-20"  # 20 October 2026 per PRD

    data = {
        "Waybill Number": [],
        "Ticket Number": [],
        "From Stop": [],
        "To Stop": [],
        "Date": [],
        "Time": [],
        "Total Psgr": [],
        "Coll Amt": [],
        "Uncoll Amt": [],
        "Unnamed: 9": []
    }

    base_ticket_counter = 500000

    for i in range(num_records):
        wb = random.choice(waybills)
        
        # Ticket number: mostly sequential, with a small percentage (0.3%) repeated across different waybills
        if random.random() < 0.003 and i > 100:
            ticket_num = f"TK{base_ticket_counter + random.randint(1, i)}"
        else:
            ticket_num = f"TK{base_ticket_counter + i}"

        # Origin and Destination
        from_stop = random.choice(major_stops)
        possible_destinations = [s for s in major_stops if s != from_stop]
        to_stop = random.choice(possible_destinations)

        # Inject ~0.25% missing stops to test data validation & data-quality reporting (FR-02)
        if random.random() < 0.0015:
            from_stop = None
        elif random.random() < 0.0015:
            to_stop = None

        # Time generation based on distribution
        hour = np.random.choice(hours, p=hour_weights)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        time_str = f"{hour:02d}:{minute:02d}:{second:02d}"

        # Passenger count per ticket: 1 (75%), 2 (18%), 3 (5%), 4 (1.5%), 5 (0.5%)
        psgr_choice = np.random.choice([1, 2, 3, 4, 5], p=[0.75, 0.18, 0.05, 0.015, 0.005])

        # Fare pricing: typical city fares ₹5, ₹10, ₹15, ₹20, ₹25, ₹30 per passenger
        base_fare = random.choice([5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
        total_fare = float(base_fare * psgr_choice)

        # Collection amount vs uncollected amount
        # Small portion (<1%) represents concessional/uncollected or partial
        if random.random() < 0.015:
            uncoll = round(float(random.choice([5.0, 10.0, total_fare])), 2)
            coll = max(0.0, total_fare - uncoll)
        else:
            coll = total_fare
            uncoll = 0.0

        # Inject an intentional operational statistical anomaly (~3 records out of 19,275 with high bulk group collection)
        if i in [1520, 8430, 14200]:
            psgr_choice = 35
            coll = 875.0
            uncoll = 0.0

        # Unnamed: 9 (Unresolved tenth column)
        # In real datasets, this might be a terminal code, checksum, or mostly NaN
        if random.random() < 0.12:
            unnamed_val = random.choice(["E", "M", "VAL_01", "VAL_02", "FLAG_A", 1, 0])
        else:
            unnamed_val = None

        data["Waybill Number"].append(wb)
        data["Ticket Number"].append(ticket_num)
        data["From Stop"].append(from_stop)
        data["To Stop"].append(to_stop)
        data["Date"].append(target_date)
        data["Time"].append(time_str)
        data["Total Psgr"].append(int(psgr_choice))
        data["Coll Amt"].append(float(coll))
        data["Uncoll Amt"].append(float(uncoll))
        data["Unnamed: 9"].append(unnamed_val)

    df = pd.DataFrame(data)

    print(f"Generated {len(df)} rows. Saving to CSV...")
    df.to_csv(csv_path, index=False)

    print(f"Saving to Excel with worksheet 'sql (12)' at {excel_path}...")
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="sql (12)", index=False)

    print("Sample generation complete!")
    return excel_path, csv_path

if __name__ == "__main__":
    generate_sample_dataset()

