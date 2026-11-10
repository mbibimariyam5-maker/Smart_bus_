"""
SmartBus Comprehensive Verification Suite
Tests Exact 10-Column Schema Enforcement, Source File Non-Modification,
Multi-Dataset Isolation, Analytics Calculations, Intelligence Engines,
and Source Data Export Integrity.
"""

import os
import io
import hashlib
import pytest
import pandas as pd
from backend.data_engine import DataEngine, EXACT_SOURCE_SCHEMA
from backend.analytics_engine import AnalyticsEngine
from backend.intelligence_engine import IntelligenceEngine
from backend.ask_smartbus import AskSmartBusEngine
from backend.export_engine import ExportEngine

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_smartbus.db")
SAMPLE_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sample", "Ticket data_1 Day_City Service.csv")

@pytest.fixture(scope="session")
def engine_suite():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    data_eng = DataEngine(db_path=TEST_DB_PATH)
    assert os.path.exists(SAMPLE_CSV_PATH), "Benchmark dataset CSV must exist"
    
    # Ingest benchmark dataset
    result = data_eng.ingest_file(SAMPLE_CSV_PATH, "Ticket data_1 Day_City Service.csv", dataset_type="DEMO_SAMPLE")
    assert result["record_count"] == 19275, "Must ingest exactly 19,275 records"

    analytics_eng = AnalyticsEngine(data_eng)
    intel_eng = IntelligenceEngine(data_eng, analytics_eng)
    ask_eng = AskSmartBusEngine(data_eng, analytics_eng, intel_eng)
    export_eng = ExportEngine(data_eng, analytics_eng, intel_eng)

    yield {
        "data_eng": data_eng,
        "analytics_eng": analytics_eng,
        "intel_eng": intel_eng,
        "ask_eng": ask_eng,
        "export_eng": export_eng,
        "dataset_id": result["dataset_id"]
    }

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

def test_exact_10_column_schema_enforcement(engine_suite):
    """
    PRD Section 5.2 & Quality Correction:
    Non-negotiable exact 10-column schema order and column count enforcement.
    """
    data_eng = engine_suite["data_eng"]

    # 1. Valid exactly 10 columns
    valid_df = pd.DataFrame(columns=EXACT_SOURCE_SCHEMA)
    is_valid, errors = data_eng.validate_schema(valid_df)
    assert is_valid is True, "Valid 10-column schema must pass"
    assert len(errors) == 0

    # 2. Extra 11th column must fail
    extra_df = pd.DataFrame(columns=EXACT_SOURCE_SCHEMA + ["Extra_Metric_11"])
    is_valid, errors = data_eng.validate_schema(extra_df)
    assert is_valid is False, "11th column must be strictly rejected"
    assert any("Expected exactly 10 columns" in e for e in errors)
    assert any("Extra column(s) detected" in e for e in errors)

    # 3. Fewer than 10 columns must fail
    fewer_df = pd.DataFrame(columns=EXACT_SOURCE_SCHEMA[:8])
    is_valid, errors = data_eng.validate_schema(fewer_df)
    assert is_valid is False, "Missing columns must be strictly rejected"
    assert any("Expected exactly 10 columns" in e for e in errors)

    # 4. Reordered columns must fail
    reordered_cols = list(EXACT_SOURCE_SCHEMA)
    # Swap position 1 (Waybill Number) and position 2 (Ticket Number)
    reordered_cols[0], reordered_cols[1] = reordered_cols[1], reordered_cols[0]
    reordered_df = pd.DataFrame(columns=reordered_cols)
    is_valid, errors = data_eng.validate_schema(reordered_df)
    assert is_valid is False, "Reordered columns must be strictly rejected"
    assert any("Column order violation" in e for e in errors)

    # 5. Renamed column must fail
    renamed_cols = list(EXACT_SOURCE_SCHEMA)
    renamed_cols[9] = "Unclassified_Flag"
    renamed_df = pd.DataFrame(columns=renamed_cols)
    is_valid, errors = data_eng.validate_schema(renamed_df)
    assert is_valid is False, "Renamed column 10 must be strictly rejected"
    assert any("Schema name violation" in e for e in errors)

def test_source_file_unmodified_on_disk():
    """
    PRD 5.3: Verify original uploaded files remain byte-for-byte unmodified.
    """
    assert os.path.exists(SAMPLE_CSV_PATH)
    with open(SAMPLE_CSV_PATH, "rb") as f:
        original_hash = hashlib.sha256(f.read()).hexdigest()

    # Re-ingest the file into a temporary data engine
    temp_db = os.path.join(os.path.dirname(__file__), "temp_audit.db")
    eng = DataEngine(db_path=temp_db)
    eng.ingest_file(SAMPLE_CSV_PATH, "Ticket data_1 Day_City Service.csv", dataset_type="DEMO_SAMPLE")

    # Verify file hash on disk is 100% identical
    with open(SAMPLE_CSV_PATH, "rb") as f:
        after_hash = hashlib.sha256(f.read()).hexdigest()

    assert original_hash == after_hash, "Original source file on disk must never be modified"

    if os.path.exists(temp_db):
        try:
            os.remove(temp_db)
        except Exception:
            pass

def test_source_data_export_exact_10_columns(engine_suite):
    """
    Requirement 2: Source-data exports must contain exactly the original 10 columns.
    """
    export_eng = engine_suite["export_eng"]
    dataset_id = engine_suite["dataset_id"]

    csv_data = export_eng.export_source_data_csv(dataset_id)
    df_exported = pd.read_csv(io.StringIO(csv_data))

    assert list(df_exported.columns) == EXACT_SOURCE_SCHEMA, "Exported source CSV must have exact 10 columns in order"
    assert len(df_exported.columns) == 10, "Exported source CSV must not have an 11th column"
    assert len(df_exported) == 19275

def test_multi_dataset_isolation_and_switching(engine_suite):
    """
    Requirement 3: Support repeated uploads without mixing records; clear active dataset switching.
    """
    data_eng = engine_suite["data_eng"]
    analytics_eng = engine_suite["analytics_eng"]
    intel_eng = engine_suite["intel_eng"]
    id_1 = engine_suite["dataset_id"]

    # Create a secondary test dataset with 50 rows and 8 days of data
    rows = []
    dates_8 = [f"2026-11-0{i}" for i in range(1, 9)]
    for i in range(50):
        rows.append({
            "Waybill Number": f"WB-SEC-{i%5}",
            "Ticket Number": f"TK-SEC-{i}",
            "From Stop": "Stop_A",
            "To Stop": "Stop_B",
            "Date": dates_8[i % 8],
            "Time": "10:30:00",
            "Total Psgr": 1,
            "Coll Amt": 25.0,
            "Uncoll Amt": 0.0,
            "Unnamed: 9": None
        })
    df_sec = pd.DataFrame(rows)
    temp_sec_csv = os.path.join(os.path.dirname(__file__), "secondary_test_dataset.csv")
    df_sec.to_csv(temp_sec_csv, index=False)

    try:
        # Ingest as DEPARTMENT_UPLOAD
        res_sec = data_eng.ingest_file(temp_sec_csv, "secondary_test_dataset.csv", dataset_type="DEPARTMENT_UPLOAD")
        id_2 = res_sec["dataset_id"]
        assert res_sec["record_count"] == 50
        assert res_sec["dataset_type"] == "DEPARTMENT_UPLOAD"

        # Check isolation: dataset 1 still has 19,275 rows
        kpis_1 = analytics_eng.get_executive_kpis(id_1)
        assert kpis_1["total_records"] == 19275

        # Dataset 2 has 50 rows
        kpis_2 = analytics_eng.get_executive_kpis(id_2)
        assert kpis_2["total_records"] == 50
        assert kpis_2["recorded_collection_amount"] == 50 * 25.0

        # Verify dataset switching
        data_eng.set_active_dataset(id_1)
        assert data_eng.get_active_dataset()["dataset_id"] == id_1
        assert data_eng.get_active_dataset()["record_count"] == 19275

        data_eng.set_active_dataset(id_2)
        assert data_eng.get_active_dataset()["dataset_id"] == id_2
        assert data_eng.get_active_dataset()["record_count"] == 50

        # Verify forecasting governance on 8-day dataset: should be eligible!
        fc_sec = intel_eng.get_forecasting(id_2)
        assert fc_sec["is_eligible"] is True, "8-day dataset must satisfy historical eligibility (>= 7 days)"
        assert fc_sec["historical_days_available"] == 8

        # Switch back to id_1 for other tests
        data_eng.set_active_dataset(id_1)
    finally:
        if os.path.exists(temp_sec_csv):
            os.remove(temp_sec_csv)

def test_schema_immutability_and_quality(engine_suite):
    """PRD 5.2, 5.3: Verify schema validation, audit trail, and quality report."""
    data_eng = engine_suite["data_eng"]
    dataset_id = engine_suite["dataset_id"]

    report = data_eng.get_quality_report(dataset_id)
    assert report["total_records"] == 19275
    assert report["distinct_tickets"] > 18000
    assert report["repeated_ticket_numbers"] >= 0
    assert report["unresolved_column_name"] == "Unnamed: 9"
    assert report["quality_score"] >= 80.0
    assert report["is_demo"] is True

    raw_df = data_eng.get_raw_dataframe(dataset_id)
    assert list(raw_df.columns) == EXACT_SOURCE_SCHEMA
    assert len(raw_df) == 19275

def test_executive_kpis(engine_suite):
    """PRD FR-03: Verify Executive Overview KPIs."""
    analytics_eng = engine_suite["analytics_eng"]
    dataset_id = engine_suite["dataset_id"]

    kpis = analytics_eng.get_executive_kpis(dataset_id)
    assert kpis["total_records"] == 19275
    assert kpis["recorded_passenger_quantity"] >= 19275
    assert kpis["recorded_collection_amount"] > 100000.0
    assert kpis["distinct_waybills"] >= 50
    assert kpis["distinct_origin_stops"] >= 15
    assert kpis["distinct_destination_stops"] >= 15
    assert kpis["avg_collection_per_ticket"] > 0
    assert kpis["avg_passengers_per_ticket"] >= 1.0

def test_passenger_and_collection_analytics(engine_suite):
    """PRD FR-04 & FR-05: Verify Passenger & Revenue breakdown."""
    analytics_eng = engine_suite["analytics_eng"]
    dataset_id = engine_suite["dataset_id"]

    psgr_data = analytics_eng.get_passenger_analytics(dataset_id, limit=5)
    assert "passenger_count_distribution" in psgr_data
    assert len(psgr_data["top_origins_by_passengers"]) == 5
    assert len(psgr_data["top_destinations_by_passengers"]) == 5
    assert len(psgr_data["top_movements_by_passengers"]) == 5
    assert psgr_data["transactions_vs_passengers_ratio"] >= 1.0

    rev_data = analytics_eng.get_revenue_analytics(dataset_id, limit=5)
    assert rev_data["total_collection"] > 0
    assert len(rev_data["top_movements_by_collection"]) == 5
    assert len(rev_data["top_waybills_by_collection"]) == 5

def test_origin_destination_intelligence(engine_suite):
    """PRD FR-06: Verify Origin-Destination pairs and flows."""
    analytics_eng = engine_suite["analytics_eng"]
    dataset_id = engine_suite["dataset_id"]

    od_data = analytics_eng.get_origin_destination_intelligence(dataset_id, limit=10)
    high_moves = od_data["high_volume_movements"]
    assert len(high_moves) == 10
    top = high_moves[0]
    assert "from_stop" in top and "to_stop" in top
    assert top["passenger_quantity"] >= high_moves[-1]["passenger_quantity"]
    assert "➔" in top["movement"]

def test_time_based_analytics_dynamic_peaks(engine_suite):
    """PRD FR-07: Verify hourly aggregation and dynamic peak detection."""
    analytics_eng = engine_suite["analytics_eng"]
    dataset_id = engine_suite["dataset_id"]

    time_data = analytics_eng.get_time_based_analytics(dataset_id)
    assert len(time_data["hourly_trends"]) > 10
    assert time_data["peak_transaction_hour"] is not None
    assert time_data["morning_peak_stats"]["total_passengers"] > 0
    assert time_data["evening_peak_stats"]["total_passengers"] > 0
    # Must have detected dynamic hours
    assert len(time_data["morning_peak_stats"]["detected_hours"]) > 0
    assert len(time_data["evening_peak_stats"]["detected_hours"]) > 0

def test_waybill_analytics(engine_suite):
    """PRD FR-08: Verify waybill metrics."""
    analytics_eng = engine_suite["analytics_eng"]
    dataset_id = engine_suite["dataset_id"]

    wb_data = analytics_eng.get_waybill_analytics(dataset_id, limit=10)
    assert wb_data["total_active_waybills"] >= 50
    assert len(wb_data["waybills"]) == 10
    top_wb = wb_data["waybills"][0]
    assert top_wb["collection_amount"] > 0
    assert top_wb["record_count"] > 0

def test_automated_insights_and_anomalies(engine_suite):
    """PRD FR-09 & FR-10: Verify structured insights and anomaly detection."""
    intel_eng = engine_suite["intel_eng"]
    dataset_id = engine_suite["dataset_id"]

    insights = intel_eng.generate_automated_insights(dataset_id)
    assert len(insights) >= 4
    for ins in insights:
        assert "finding" in ins
        assert "supporting_metric" in ins
        assert "dataset_scope" in ins
        assert "limitations" in ins

    anomalies = intel_eng.detect_anomalies(dataset_id)
    assert len(anomalies) > 0
    types = set(a["anomaly_type"] for a in anomalies)
    assert "Data Quality" in types
    assert "Operational Statistical" in types

def test_forecasting_governance_single_day(engine_suite):
    """PRD FR-11: Verify single-day governance lockout and simulation mode."""
    intel_eng = engine_suite["intel_eng"]
    dataset_id = engine_suite["dataset_id"]

    locked_fc = intel_eng.get_forecasting(dataset_id, enable_simulation=False)
    assert locked_fc["is_eligible"] is False
    assert locked_fc["historical_days_available"] == 1
    assert "HISTORICAL FORECASTING GOVERNANCE NOTICE" in locked_fc["governance_notice"]
    assert len(locked_fc["forecast_points"]) == 0

    sim_fc = intel_eng.get_forecasting(dataset_id, enable_simulation=True)
    assert len(sim_fc["forecast_points"]) == 7
    assert sim_fc["demonstration_mode"] is True
    assert "Demonstration Simulation" in sim_fc["forecast_points"][0]["mode"]

def test_ask_smartbus(engine_suite):
    """PRD FR-13: Verify natural language query grounding."""
    ask_eng = engine_suite["ask_eng"]
    dataset_id = engine_suite["dataset_id"]

    res1 = ask_eng.process_query("Which hour recorded the highest transaction volume?", dataset_id)
    assert "peak hour for ticket transactions" in res1["answer"].lower()
    assert res1["analytical_tool_used"] != ""

    res2 = ask_eng.process_query("Which origin-destination pair has the highest recorded passenger quantity?", dataset_id)
    assert "origin–destination pair" in res2["answer"].lower() or "highest" in res2["answer"].lower()
    assert "➔" in res2["answer"]

    res3 = ask_eng.process_query("What is the total recorded collection?", dataset_id)
    assert "total recorded collection" in res3["answer"].lower()
    assert "Coll Amt" in res3["answer"]

def test_forecasting_target_dataset_metadata_isolation(engine_suite):
    """Regression test for Task 4: Inactive dataset forecasting metadata isolation."""
    data_eng = engine_suite["data_eng"]
    intel_eng = engine_suite["intel_eng"]
    active_dataset_id = engine_suite["dataset_id"]

    # Ingest a temporary 7-day dataset B
    import tempfile
    import pandas as pd
    with tempfile.TemporaryDirectory() as tmp_dir:
        dates_b = [f"2026-06-{i+1:02d}" for i in range(8)]
        rows = []
        for idx, d in enumerate(dates_b):
            rows.append({
                "Waybill Number": "WB-ISO",
                "Ticket Number": f"TK-ISO-{idx}",
                "From Stop": "Alpha",
                "To Stop": "Beta",
                "Date": d,
                "Time": "10:00:00",
                "Total Psgr": 5,
                "Coll Amt": 100.0,
                "Uncoll Amt": 0.0,
                "Unnamed: 9": None
            })
        csv_b = os.path.join(tmp_dir, "dataset_b.csv")
        pd.DataFrame(rows).to_csv(csv_b, index=False)
        res_b = data_eng.ingest_file(csv_b, "dataset_b.csv")
        id_b = res_b["dataset_id"]

        # Switch active dataset BACK to active_dataset_id (which has 1 date)
        data_eng.set_active_dataset(active_dataset_id)
        assert data_eng.get_active_dataset()["dataset_id"] == active_dataset_id
        assert data_eng.get_active_dataset()["distinct_dates"] == 1

        # Query forecasting for id_b explicitly while active_dataset_id is active
        fc_b = intel_eng.get_forecasting(dataset_id=id_b, enable_simulation=False)
        assert fc_b["historical_days_available"] == 8
        assert fc_b["is_eligible"] is True
        assert len(fc_b["forecast_points"]) == 7

        # Query forecasting for active_dataset_id explicitly while active_dataset_id is active
        fc_active = intel_eng.get_forecasting(dataset_id=active_dataset_id, enable_simulation=False)
        assert fc_active["historical_days_available"] == 1
        assert fc_active["is_eligible"] is False
        assert len(fc_active["forecast_points"]) == 0

def test_exports(engine_suite):
    """Verify CSV and PDF export generation."""
    export_eng = engine_suite["export_eng"]
    dataset_id = engine_suite["dataset_id"]

    od_csv = export_eng.export_od_csv(dataset_id)
    assert "From Stop,To Stop,Movement" in od_csv

    wb_csv = export_eng.export_waybill_csv(dataset_id)
    assert "Waybill Number,Record Count" in wb_csv

    pdf_bytes = export_eng.generate_executive_pdf(dataset_id)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")
