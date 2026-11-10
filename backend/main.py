"""
SmartBus FastAPI Main Application Entrypoint
Provides RESTful APIs for Analytics, Data Quality, Intelligence, and Conversational Querying.
Serves the Karnataka Transport Executive Dashboard frontend.
"""

import os
import shutil
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse

from backend.data_engine import DataEngine
from backend.analytics_engine import AnalyticsEngine
from backend.intelligence_engine import IntelligenceEngine
from backend.ask_smartbus import AskSmartBusEngine
from backend.export_engine import ExportEngine
from backend.models import AskSmartBusRequest

app = FastAPI(
    title="SmartBus API",
    description="Karnataka Intelligent Bus Transport Analytics Platform API",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_engine = DataEngine()
analytics_engine = AnalyticsEngine(data_engine)
intelligence_engine = IntelligenceEngine(data_engine, analytics_engine)
ask_engine = AskSmartBusEngine(data_engine, analytics_engine, intelligence_engine)
export_engine = ExportEngine(data_engine, analytics_engine, intelligence_engine)

# Note: No sample datasets are auto-ingested on startup.
# The application maintains a clean first-time experience with NO active dataset by default.
# Datasets are ingested only when explicitly uploaded by the user.

# ----------------- DATASET MANAGEMENT APIS -----------------

@app.post("/api/dataset/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """
    Uploads an actual transport department Excel or CSV dataset with strict 10-column schema validation.
    Preserves original uploaded file unmodified.
    Flagged as DEPARTMENT_UPLOAD.
    """
    filename = file.filename or "uploaded_dataset"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".xlsx", ".xls", ".csv"]:
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, and .csv files are supported.")

    raw_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    saved_path = os.path.join(raw_dir, filename)

    # Save original file byte-for-byte unmodified
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = data_engine.ingest_file(saved_path, filename, dataset_type="DEPARTMENT_UPLOAD")
        return {
            "status": "success",
            "message": f"Dataset '{filename}' successfully verified against strict 10-column schema and ingested ({result['record_count']:,} records).",
            "data": result
        }
    except Exception as e:
        if os.path.exists(saved_path):
            os.remove(saved_path)
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/dataset/info")
def get_dataset_info(dataset_id: Optional[str] = None):
    info = data_engine.get_active_dataset()
    if not info:
        return {"has_active_dataset": False}
    return {"has_active_dataset": True, "dataset": info}

@app.get("/api/dataset/list")
def list_datasets():
    return {"datasets": data_engine.list_datasets()}

@app.post("/api/dataset/set-active/{dataset_id}")
def set_active_dataset(dataset_id: str):
    try:
        data_engine.set_active_dataset(dataset_id)
        return {"status": "success", "active_dataset_id": dataset_id}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/dataset/deactivate")
def deactivate_active_dataset():
    data_engine.deactivate_active_dataset()
    return {"status": "success", "message": "Active dataset has been deactivated. SmartBus is in initial welcome state."}

@app.post("/api/dataset/deactivate/{dataset_id}")
def deactivate_dataset(dataset_id: str):
    data_engine.deactivate_dataset(dataset_id)
    return {"status": "success", "message": f"Dataset '{dataset_id}' has been deactivated."}

@app.get("/api/dataset/quality-report")
def get_quality_report(dataset_id: Optional[str] = None):
    try:
        report = data_engine.get_quality_report(dataset_id)
        return report
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/dataset/audit-logs")
def get_audit_logs(dataset_id: Optional[str] = None):
    return {"logs": data_engine.get_audit_logs(dataset_id)}

# ----------------- CORE ANALYTICS APIS -----------------

@app.get("/api/analytics/executive")
def get_executive_kpis(dataset_id: Optional[str] = None, waybill: Optional[str] = None):
    return analytics_engine.get_executive_kpis(dataset_id, waybill_filter=waybill)

@app.get("/api/analytics/passenger")
def get_passenger_analytics(dataset_id: Optional[str] = None, limit: int = 10):
    return analytics_engine.get_passenger_analytics(dataset_id, limit=limit)

@app.get("/api/analytics/revenue")
def get_revenue_analytics(dataset_id: Optional[str] = None, limit: int = 10):
    return analytics_engine.get_revenue_analytics(dataset_id, limit=limit)

@app.get("/api/analytics/origin-destination")
def get_origin_destination_analytics(dataset_id: Optional[str] = None, limit: int = 15):
    return analytics_engine.get_origin_destination_intelligence(dataset_id, limit=limit)

@app.get("/api/analytics/time-based")
def get_time_based_analytics(dataset_id: Optional[str] = None):
    return analytics_engine.get_time_based_analytics(dataset_id)

@app.get("/api/analytics/waybills")
def get_waybill_analytics(dataset_id: Optional[str] = None, limit: int = 50):
    return analytics_engine.get_waybill_analytics(dataset_id, limit=limit)

# ----------------- INTELLIGENCE APIS -----------------

@app.get("/api/intelligence/insights")
def get_automated_insights(dataset_id: Optional[str] = None):
    return {"insights": intelligence_engine.generate_automated_insights(dataset_id)}

@app.get("/api/intelligence/anomalies")
def get_anomalies(dataset_id: Optional[str] = None):
    return {"anomalies": intelligence_engine.detect_anomalies(dataset_id)}

@app.get("/api/intelligence/forecasting")
def get_forecasting(dataset_id: Optional[str] = None, enable_simulation: bool = Query(False)):
    return intelligence_engine.get_forecasting(dataset_id, enable_simulation=enable_simulation)

@app.get("/api/intelligence/recommendations")
def get_recommendations(dataset_id: Optional[str] = None):
    return {"recommendations": intelligence_engine.generate_recommendations(dataset_id)}

# ----------------- CONVERSATIONAL ASK SMARTBUS -----------------

@app.post("/api/ask-smartbus")
def ask_smartbus(req: AskSmartBusRequest):
    return ask_engine.process_query(req.query, req.dataset_id)

# ----------------- EXPORT APIS -----------------

@app.get("/api/export/source-data-csv")
def export_source_data_csv(dataset_id: Optional[str] = None):
    """
    Exports the verified raw source data containing strictly the 10 immutable columns:
    1. Waybill Number, 2. Ticket Number, 3. From Stop, 4. To Stop, 5. Date,
    6. Time, 7. Total Psgr, 8. Coll Amt, 9. Uncoll Amt, 10. Unnamed: 9
    """
    try:
        csv_str = export_engine.export_source_data_csv(dataset_id)
        return PlainTextResponse(
            content=csv_str,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=SmartBus_Verified_Source_Data_10Cols.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/export/od-csv")
def export_od_csv(dataset_id: Optional[str] = None):
    csv_str = export_engine.export_od_csv(dataset_id)
    return PlainTextResponse(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=SmartBus_Origin_Destination_Analysis.csv"}
    )

@app.get("/api/export/waybill-csv")
def export_waybill_csv(dataset_id: Optional[str] = None):
    csv_str = export_engine.export_waybill_csv(dataset_id)
    return PlainTextResponse(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=SmartBus_Waybill_Operational_Metrics.csv"}
    )

@app.get("/api/export/hourly-csv")
def export_hourly_csv(dataset_id: Optional[str] = None):
    csv_str = export_engine.export_hourly_csv(dataset_id)
    return PlainTextResponse(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=SmartBus_Hourly_Time_Trends.csv"}
    )

@app.get("/api/export/executive-pdf")
def export_executive_pdf(dataset_id: Optional[str] = None):
    pdf_bytes = export_engine.generate_executive_pdf(dataset_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=SmartBus_Executive_Briefing.pdf"}
    )

# ----------------- STATIC FRONTEND SERVING -----------------

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_dir, "static")), name="static")

    @app.get("/")
    def serve_frontend_index():
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "SmartBus backend operational. Frontend index.html not found."}
