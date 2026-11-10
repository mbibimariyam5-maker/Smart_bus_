"""
Direct unit tests for backend API route handler functions.
Invokes route functions directly without starlette.testclient.
"""

import os
import pytest
from backend.main import (
    get_dataset_info,
    list_datasets,
    get_quality_report,
    get_executive_kpis,
    get_passenger_analytics,
    get_revenue_analytics,
    get_origin_destination_analytics,
    get_time_based_analytics,
    get_waybill_analytics,
    get_automated_insights,
    get_anomalies,
    get_forecasting,
    get_recommendations,
    ask_smartbus,
    export_source_data_csv,
    export_od_csv,
    export_waybill_csv,
    export_executive_pdf,
    data_engine
)
from backend.models import AskSmartBusRequest
from backend.data_engine import EXACT_SOURCE_SCHEMA

@pytest.fixture(autouse=True, scope="module")
def ensure_active_test_dataset():
    """Ensures a dataset is active for API route testing without hardcoding it in production startup, and restores clean state on teardown."""
    prev_active = data_engine.get_active_dataset()
    created_id = None
    if not prev_active:
        # Check if an existing dataset is already in repo to activate
        all_ds = data_engine.list_datasets()
        if all_ds:
            data_engine.set_active_dataset(all_ds[0]["dataset_id"])
        else:
            sample_csv = os.path.join(os.path.dirname(__file__), "..", "data", "sample", "Ticket data_1 Day_City Service.csv")
            res = data_engine.ingest_file(sample_csv, "Ticket data_1 Day_City Service.csv", dataset_type="DEPARTMENT_UPLOAD")
            created_id = res["dataset_id"]
    yield
    # Restore previous state
    if prev_active:
        data_engine.set_active_dataset(prev_active["dataset_id"])
    else:
        data_engine.deactivate_active_dataset()


def test_api_dataset_info():
    info = get_dataset_info()
    assert info["has_active_dataset"] is True
    assert info["dataset"]["record_count"] == 19275
    assert "dataset_type" in info["dataset"]

def test_api_list_datasets():
    res = list_datasets()
    assert "datasets" in res
    assert len(res["datasets"]) >= 1
    ds = res["datasets"][0]
    assert "dataset_type" in ds
    assert "is_demo" in ds

def test_api_quality_report():
    q = get_quality_report()
    assert q["total_records"] == 19275
    assert q["quality_score"] > 80.0
    assert q["unresolved_column_name"] == "Unnamed: 9"

def test_api_executive_kpis():
    kpis = get_executive_kpis()
    assert kpis["total_records"] == 19275
    assert kpis["recorded_passenger_quantity"] > 19275
    assert kpis["recorded_collection_amount"] > 80000.0

def test_api_passenger_analytics():
    psgr = get_passenger_analytics(limit=5)
    assert len(psgr["top_origins_by_passengers"]) == 5
    assert len(psgr["top_destinations_by_passengers"]) == 5

def test_api_revenue_analytics():
    rev = get_revenue_analytics(limit=5)
    assert rev["total_collection"] > 0
    assert len(rev["top_waybills_by_collection"]) == 5

def test_api_od_analytics():
    od = get_origin_destination_analytics(limit=10)
    assert len(od["high_volume_movements"]) == 10
    assert "movement" in od["high_volume_movements"][0]

def test_api_time_analytics():
    time_res = get_time_based_analytics()
    assert len(time_res["hourly_trends"]) > 0
    assert time_res["peak_transaction_hour"] is not None

def test_api_waybill_analytics():
    wb = get_waybill_analytics(limit=10)
    assert len(wb["waybills"]) == 10
    assert wb["total_active_waybills"] >= 40

def test_api_insights():
    ins = get_automated_insights()
    assert len(ins["insights"]) >= 4

def test_api_anomalies():
    anom = get_anomalies()
    assert len(anom["anomalies"]) > 0

def test_api_forecasting():
    # Locked
    fc1 = get_forecasting(enable_simulation=False)
    assert fc1["is_eligible"] is False
    assert len(fc1["forecast_points"]) == 0

    # Simulation unlocked
    fc2 = get_forecasting(enable_simulation=True)
    assert len(fc2["forecast_points"]) == 7

def test_api_recommendations():
    recs = get_recommendations()
    assert len(recs["recommendations"]) >= 3

def test_api_ask_smartbus():
    req = AskSmartBusRequest(query="Which origin-destination pair has the highest recorded passenger quantity?")
    res = ask_smartbus(req)
    assert "highest recorded passenger volume" in res["answer"].lower()
    assert res["confidence"] != ""

def test_api_exports():
    # Exact 10-column source export
    res_source = export_source_data_csv()
    first_line = res_source.body.decode().splitlines()[0]
    expected_header = ",".join(EXACT_SOURCE_SCHEMA)
    assert first_line == expected_header, "Source export must have exact 10 columns in order"

    # Analytical exports
    res_csv = export_od_csv()
    assert "From Stop,To Stop,Movement" in res_csv.body.decode()

    res_pdf = export_executive_pdf()
    assert res_pdf.body.startswith(b"%PDF")
