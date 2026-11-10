"""
SmartBus Pydantic Data Models & Schemas
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class DatasetInfo(BaseModel):
    dataset_id: str
    filename: str
    record_count: int
    column_count: int
    columns: List[str]
    distinct_dates: int
    dates: List[str]
    is_active: bool
    upload_timestamp: str

class DataQualityReport(BaseModel):
    dataset_id: str
    filename: str
    total_records: int
    missing_from_stops: int
    missing_to_stops: int
    repeated_ticket_numbers: int
    distinct_tickets: int
    distinct_waybills: int
    distinct_origins: int
    distinct_destinations: int
    unresolved_column_name: str
    unresolved_column_non_nulls: int
    unresolved_column_nulls: int
    unresolved_column_unique_values: int
    invalid_passenger_records: int
    zero_or_negative_collection_records: int
    warnings: List[str]
    quality_score: float

class ExecutiveKPIs(BaseModel):
    total_records: int
    distinct_tickets: int
    recorded_passenger_quantity: int
    recorded_collection_amount: float
    recorded_uncollected_amount: float
    distinct_waybills: int
    distinct_origin_stops: int
    distinct_destination_stops: int
    avg_collection_per_ticket: float
    avg_passengers_per_ticket: float

class PassengerAnalytics(BaseModel):
    passenger_count_distribution: Dict[str, int]
    top_origins_by_passengers: List[Dict[str, Any]]
    top_destinations_by_passengers: List[Dict[str, Any]]
    top_movements_by_passengers: List[Dict[str, Any]]
    transactions_vs_passengers_ratio: float

class RevenueAnalytics(BaseModel):
    total_collection: float
    total_uncollected: float
    collection_distribution: Dict[str, int]
    top_movements_by_collection: List[Dict[str, Any]]
    top_waybills_by_collection: List[Dict[str, Any]]
    uncollected_by_waybill: List[Dict[str, Any]]

class OriginDestinationMovement(BaseModel):
    from_stop: str
    to_stop: str
    movement: str
    transaction_count: int
    passenger_quantity: int
    collection_amount: float
    avg_collection_per_passenger: float

class HourlyAnalytics(BaseModel):
    hourly_trends: List[Dict[str, Any]]
    peak_transaction_hour: str
    peak_passenger_hour: str
    peak_collection_hour: str
    trough_hour: str
    morning_peak_stats: Dict[str, Any]
    evening_peak_stats: Dict[str, Any]

class WaybillMetric(BaseModel):
    waybill_number: str
    record_count: int
    passenger_quantity: int
    collection_amount: float
    uncollected_amount: float
    active_hours_count: int
    first_transaction_time: str
    last_transaction_time: str

class AutomatedInsight(BaseModel):
    id: str
    category: str
    finding: str
    supporting_metric: str
    baseline_or_comparison: str
    dataset_scope: str
    limitations: str
    confidence: str

class AnomalyItem(BaseModel):
    id: str
    anomaly_type: str  # 'Data Quality' or 'Operational Statistical'
    entity_type: str   # 'Waybill', 'Ticket', 'Stop', 'Time'
    entity_id: str
    description: str
    severity: str      # 'High', 'Medium', 'Low'
    observed_value: Any
    expected_range: str
    statistical_method: str

class Recommendation(BaseModel):
    id: str
    category: str
    title: str
    action_item: str
    supporting_evidence: str
    limitations_and_prerequisites: str
    impact_level: str

class ForecastResponse(BaseModel):
    is_eligible: bool
    governance_notice: str
    historical_days_available: int
    required_days: int
    demonstration_mode: bool
    forecast_points: List[Dict[str, Any]] = []

class AskSmartBusRequest(BaseModel):
    query: str
    dataset_id: Optional[str] = None

class AskSmartBusResponse(BaseModel):
    query: str
    answer: str
    grounded_metrics: Dict[str, Any]
    analytical_tool_used: str
    confidence: str
    notes_and_limitations: str

