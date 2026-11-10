"""
SmartBus Safe Dataset Deactivation Utility
Safely inspects datasets_meta and deactivates demo/sample datasets.
Preserves all genuine user uploads, raw tickets, and reference files.
Does not delete any data or clear the database blindly.
"""

import os
import sys
import sqlite3
import argparse

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "smartbus.db")

def inspect_and_deactivate(deactivate_all: bool = False, deactivate_demo_only: bool = True):
    if not os.path.exists(DB_PATH):
        print(f"[SmartBus] Database not found at: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 65)
    print(" SmartBus Dataset Metadata Inspection & Safe Deactivation")
    print("=" * 65)

    cursor.execute("SELECT dataset_id, filename, dataset_type, record_count, is_active, created_at FROM datasets_meta")
    rows = cursor.fetchall()

    if not rows:
        print("[SmartBus] No datasets registered in database.")
        conn.close()
        return

    print(f"Total datasets registered: {len(rows)}\n")
    for r in rows:
        status = "ACTIVE" if r["is_active"] else "INACTIVE"
        print(f" • ID: {r['dataset_id']}")
        print(f"   File: {r['filename']} | Type: {r['dataset_type']} | Records: {r['record_count']:,} | Status: [{status}]")

    print("-" * 65)

    if deactivate_all:
        cursor.execute("UPDATE datasets_meta SET is_active = 0")
        conn.commit()
        print("[SmartBus] SUCCESS: All datasets safely deactivated (is_active = 0).")
        print("[SmartBus] No raw records or files were deleted. All datasets preserved in repository.")
        print("[SmartBus] Next website launch will open cleanly into the Welcome Screen.")
    elif deactivate_demo_only:
        cursor.execute("UPDATE datasets_meta SET is_active = 0 WHERE dataset_type = 'DEMO_SAMPLE'")
        affected = cursor.rowcount
        conn.commit()
        print(f"[SmartBus] SUCCESS: Deactivated {affected} DEMO_SAMPLE dataset(s).")
        print("[SmartBus] Genuine user-uploaded datasets remain untouched.")

    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safely deactivate demo or all datasets in SmartBus.")
    parser.add_argument("--all", action="store_true", help="Deactivate all datasets to start cleanly on the Welcome Screen.")
    args = parser.parse_args()

    inspect_and_deactivate(deactivate_all=args.all, deactivate_demo_only=not args.all)

