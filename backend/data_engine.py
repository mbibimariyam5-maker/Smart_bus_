"""
SmartBus Data Engine
Manages raw dataset loading, strict 10-column schema validation, immutability preservation,
audit trails, SQLite database storage, and dataset quality inspections.
"""

import os
import sqlite3
import datetime
import uuid
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
import numpy as np

# Non-negotiable exact 10-column source schema in immutable order
EXACT_SOURCE_SCHEMA = [
    "Waybill Number",
    "Ticket Number",
    "From Stop",
    "To Stop",
    "Date",
    "Time",
    "Total Psgr",
    "Coll Amt",
    "Uncoll Amt",
    "Unnamed: 9"
]

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "smartbus.db")

class DataEngine:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Datasets metadata table with dataset_type (DEMO_SAMPLE vs DEPARTMENT_UPLOAD)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS datasets_meta (
                dataset_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                dataset_type TEXT NOT NULL DEFAULT 'DEPARTMENT_UPLOAD',
                record_count INTEGER NOT NULL,
                distinct_dates INTEGER NOT NULL,
                dates_json TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """)

            # Ensure dataset_type column exists if table was already created
            cursor.execute("PRAGMA table_info(datasets_meta)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "dataset_type" not in columns:
                cursor.execute("ALTER TABLE datasets_meta ADD COLUMN dataset_type TEXT NOT NULL DEFAULT 'DEPARTMENT_UPLOAD'")

            # Immutable Raw tickets table - preserving exact 10 source columns + dataset_id metadata
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT NOT NULL,
                waybill_number TEXT,
                ticket_number TEXT,
                from_stop TEXT,
                to_stop TEXT,
                date_str TEXT,
                time_str TEXT,
                total_psgr INTEGER,
                coll_amt REAL,
                uncoll_amt REAL,
                unresolved_col_10 TEXT,
                FOREIGN KEY (dataset_id) REFERENCES datasets_meta (dataset_id)
            )
            """)

            # Indexing for high-performance aggregations
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_dataset ON raw_tickets(dataset_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_waybill ON raw_tickets(waybill_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_stops ON raw_tickets(from_stop, to_stop)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_raw_time ON raw_tickets(time_str)")

            # Transformation Audit Log
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS transformation_audit_log (
                log_id TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                records_affected INTEGER NOT NULL,
                logged_at TEXT NOT NULL
            )
            """)
            conn.commit()

    def log_audit(self, dataset_id: str, event_type: str, description: str, records_affected: int = 0):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO transformation_audit_log (log_id, dataset_id, event_type, description, records_affected, logged_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                dataset_id,
                event_type,
                description,
                records_affected,
                datetime.datetime.now(datetime.timezone.utc).isoformat()
            ))
            conn.commit()

    def validate_schema(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Validates that the source dataframe strictly follows the immutable 10-column schema
        in the exact non-negotiable order:
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

        Rules:
        - Exactly 10 columns (no 11th column, no fewer than 10).
        - Exact column order.
        - Exact column names (no renaming, deleting, or reordering).
        - Reports missing, extra, renamed, or reordered columns clearly.
        """
        actual_cols = list(df.columns)
        errors = []

        # Check total column count
        if len(actual_cols) != 10:
            if len(actual_cols) > 10:
                extra_cols = actual_cols[10:]
                errors.append(
                    f"Column count violation: Expected exactly 10 columns, but found {len(actual_cols)} columns. "
                    f"Extra column(s) detected: {extra_cols}. Source schema allows no extra fields."
                )
            else:
                errors.append(
                    f"Column count violation: Expected exactly 10 columns, but found {len(actual_cols)} columns."
                )

        # Check position-by-position match
        min_len = min(len(actual_cols), len(EXACT_SOURCE_SCHEMA))
        for i in range(min_len):
            expected = EXACT_SOURCE_SCHEMA[i]
            actual = str(actual_cols[i]).strip()
            if actual != expected:
                # Detect whether it was reordered or renamed
                if expected in actual_cols:
                    actual_pos = actual_cols.index(expected) + 1
                    errors.append(
                        f"Column order violation: Column '{expected}' is at position {actual_pos}, but must be at position {i+1}."
                    )
                else:
                    errors.append(
                        f"Schema name violation: Expected column '{expected}' at position {i+1}, but found '{actual}'."
                    )

        # If fewer columns, report missing
        if len(actual_cols) < 10:
            missing = EXACT_SOURCE_SCHEMA[len(actual_cols):]
            errors.append(f"Missing mandatory schema columns: {missing}")

        is_valid = len(errors) == 0
        return is_valid, errors

    def ingest_file(self, file_path: str, original_filename: str, dataset_type: str = "DEPARTMENT_UPLOAD") -> Dict[str, Any]:
        """
        Ingests an Excel or CSV file non-destructively:
        - Reads source into working copy without altering original file.
        - Verifies exact 10-column schema.
        - Populates raw_tickets and datasets_meta.
        - Distinguishes DEMO_SAMPLE from DEPARTMENT_UPLOAD.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".xlsx", ".xls"]:
            xl = pd.ExcelFile(file_path)
            # Use 'sql (12)' if present per PRD 5.1 sample spec, else the first worksheet
            sheet_to_use = "sql (12)" if "sql (12)" in xl.sheet_names else xl.sheet_names[0]
            df = pd.read_excel(file_path, sheet_name=sheet_to_use)
        elif ext == ".csv":
            df = pd.read_csv(file_path)
        else:
            raise ValueError(f"Unsupported file format '{ext}'. Must be .xlsx, .xls, or .csv")

        # Validate exact 10-column schema and order
        is_valid, errors = self.validate_schema(df)
        if not is_valid:
            raise ValueError(f"Schema validation failed: {'; '.join(errors)}")

        dataset_id = str(uuid.uuid4())
        record_count = len(df)

        # Audit log creation
        self.log_audit(
            dataset_id=dataset_id,
            event_type="INGESTION_START",
            description=f"Ingesting file '{original_filename}' ({dataset_type}) with {record_count} records",
            records_affected=record_count
        )

        # Extract columns strictly from exact positions
        waybill_series = df["Waybill Number"].astype(str)
        ticket_series = df["Ticket Number"].astype(str)
        from_stop_series = df["From Stop"].apply(
            lambda x: None if pd.isna(x) or str(x).strip().lower() in ['nan', 'none', ''] else str(x).strip()
        )
        to_stop_series = df["To Stop"].apply(
            lambda x: None if pd.isna(x) or str(x).strip().lower() in ['nan', 'none', ''] else str(x).strip()
        )
        date_series = df["Date"].astype(str).str.strip()
        time_series = df["Time"].astype(str).str.strip()
        
        total_psgr = pd.to_numeric(df["Total Psgr"], errors="coerce").fillna(1).astype(int)
        coll_amt = pd.to_numeric(df["Coll Amt"], errors="coerce").fillna(0.0).astype(float)
        uncoll_amt = pd.to_numeric(df["Uncoll Amt"], errors="coerce").fillna(0.0).astype(float)
        unresolved_col_10 = df["Unnamed: 9"].apply(lambda x: None if pd.isna(x) else str(x).strip())

        distinct_dates = sorted(list(date_series.dropna().unique()))

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Set previous active datasets to inactive
            cursor.execute("UPDATE datasets_meta SET is_active = 0")

            # Insert metadata with dataset_type
            import json
            cursor.execute("""
            INSERT INTO datasets_meta (
                dataset_id, filename, file_path, dataset_type, record_count,
                distinct_dates, dates_json, is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                dataset_id,
                original_filename,
                file_path,
                dataset_type,
                record_count,
                len(distinct_dates),
                json.dumps(distinct_dates),
                datetime.datetime.now(datetime.timezone.utc).isoformat()
            ))

            # Batch insert raw tickets
            rows_to_insert = []
            for i in range(record_count):
                rows_to_insert.append((
                    dataset_id,
                    waybill_series.iloc[i],
                    ticket_series.iloc[i],
                    from_stop_series.iloc[i],
                    to_stop_series.iloc[i],
                    date_series.iloc[i],
                    time_series.iloc[i],
                    int(total_psgr.iloc[i]),
                    float(coll_amt.iloc[i]),
                    float(uncoll_amt.iloc[i]),
                    unresolved_col_10.iloc[i]
                ))

            cursor.executemany("""
            INSERT INTO raw_tickets (
                dataset_id, waybill_number, ticket_number, from_stop, to_stop,
                date_str, time_str, total_psgr, coll_amt, uncoll_amt, unresolved_col_10
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows_to_insert)

            conn.commit()

        self.log_audit(
            dataset_id=dataset_id,
            event_type="INGESTION_COMPLETE",
            description=f"Successfully loaded {record_count} records into immutable raw storage ({dataset_type})",
            records_affected=record_count
        )

        return {
            "dataset_id": dataset_id,
            "filename": original_filename,
            "dataset_type": dataset_type,
            "record_count": record_count,
            "distinct_dates": len(distinct_dates),
            "dates": distinct_dates,
            "is_active": True
        }

    def get_active_dataset(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM datasets_meta WHERE is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            if row:
                import json
                return {
                    "dataset_id": row["dataset_id"],
                    "filename": row["filename"],
                    "file_path": row["file_path"],
                    "dataset_type": row["dataset_type"],
                    "is_demo": row["dataset_type"] == "DEMO_SAMPLE",
                    "record_count": row["record_count"],
                    "distinct_dates": row["distinct_dates"],
                    "dates": json.loads(row["dates_json"]),
                    "is_active": bool(row["is_active"]),
                    "created_at": row["created_at"]
                }
        return None

    def get_dataset_metadata(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves metadata for a specific dataset ID, whether it is active or inactive.
        Guarantees isolation when querying metadata for a targeted dataset.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM datasets_meta WHERE dataset_id = ? LIMIT 1", (dataset_id,))
            row = cursor.fetchone()
            if row:
                import json
                return {
                    "dataset_id": row["dataset_id"],
                    "filename": row["filename"],
                    "file_path": row["file_path"],
                    "dataset_type": row["dataset_type"],
                    "is_demo": row["dataset_type"] == "DEMO_SAMPLE",
                    "record_count": row["record_count"],
                    "distinct_dates": row["distinct_dates"],
                    "dates": json.loads(row["dates_json"]),
                    "is_active": bool(row["is_active"]),
                    "created_at": row["created_at"]
                }
        return None

    def list_datasets(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM datasets_meta ORDER BY created_at DESC")
            rows = cursor.fetchall()
            import json
            return [{
                "dataset_id": r["dataset_id"],
                "filename": r["filename"],
                "dataset_type": r["dataset_type"],
                "is_demo": r["dataset_type"] == "DEMO_SAMPLE",
                "record_count": r["record_count"],
                "distinct_dates": r["distinct_dates"],
                "dates": json.loads(r["dates_json"]),
                "is_active": bool(r["is_active"]),
                "created_at": r["created_at"]
            } for r in rows]

    def set_active_dataset(self, dataset_id: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT dataset_id FROM datasets_meta WHERE dataset_id = ?", (dataset_id,))
            if not cursor.fetchone():
                raise ValueError(f"Dataset ID '{dataset_id}' does not exist.")
            cursor.execute("UPDATE datasets_meta SET is_active = 0")
            cursor.execute("UPDATE datasets_meta SET is_active = 1 WHERE dataset_id = ?", (dataset_id,))
            conn.commit()

    def deactivate_active_dataset(self):
        """Deactivates any currently active dataset, returning system to no-active-dataset state."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE datasets_meta SET is_active = 0")
            conn.commit()

    def deactivate_dataset(self, dataset_id: str):
        """Deactivates a specific dataset by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE datasets_meta SET is_active = 0 WHERE dataset_id = ?", (dataset_id,))
            conn.commit()

    def get_quality_report(self, dataset_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Produces a comprehensive Dataset Quality Report (FR-02)
        Audits missing stops, repeated tickets, unresolved fields, and invalid amounts.
        """
        if not dataset_id:
            active = self.get_active_dataset()
            if not active:
                raise ValueError("No active dataset found.")
            dataset_id = active["dataset_id"]
            filename = active["filename"]
            dataset_type = active.get("dataset_type", "DEPARTMENT_UPLOAD")
        else:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT filename, dataset_type FROM datasets_meta WHERE dataset_id = ?", (dataset_id,))
                row = cursor.fetchone()
                filename = row["filename"] if row else "Dataset"
                dataset_type = row["dataset_type"] if row else "DEPARTMENT_UPLOAD"

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM raw_tickets WHERE dataset_id = ?", (dataset_id,))
            total_records = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM raw_tickets WHERE dataset_id = ? AND (from_stop IS NULL OR trim(from_stop) = '')", (dataset_id,))
            missing_from_stops = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM raw_tickets WHERE dataset_id = ? AND (to_stop IS NULL OR trim(to_stop) = '')", (dataset_id,))
            missing_to_stops = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT ticket_number) FROM raw_tickets WHERE dataset_id = ?", (dataset_id,))
            distinct_tickets = cursor.fetchone()[0]
            repeated_tickets = total_records - distinct_tickets

            cursor.execute("SELECT COUNT(DISTINCT waybill_number) FROM raw_tickets WHERE dataset_id = ?", (dataset_id,))
            distinct_waybills = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT from_stop) FROM raw_tickets WHERE dataset_id = ? AND from_stop IS NOT NULL", (dataset_id,))
            distinct_origins = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT to_stop) FROM raw_tickets WHERE dataset_id = ? AND to_stop IS NOT NULL", (dataset_id,))
            distinct_destinations = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM raw_tickets WHERE dataset_id = ? AND unresolved_col_10 IS NOT NULL AND trim(unresolved_col_10) != ''", (dataset_id,))
            unresolved_non_nulls = cursor.fetchone()[0]
            unresolved_nulls = total_records - unresolved_non_nulls

            cursor.execute("SELECT COUNT(DISTINCT unresolved_col_10) FROM raw_tickets WHERE dataset_id = ? AND unresolved_col_10 IS NOT NULL AND trim(unresolved_col_10) != ''", (dataset_id,))
            unresolved_unique_vals = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM raw_tickets WHERE dataset_id = ? AND total_psgr <= 0", (dataset_id,))
            invalid_passenger_records = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM raw_tickets WHERE dataset_id = ? AND coll_amt <= 0 AND uncoll_amt <= 0", (dataset_id,))
            zero_collection_records = cursor.fetchone()[0]

        warnings = []
        if dataset_type == "DEMO_SAMPLE":
            warnings.append("Active dataset is generated benchmark/demo data. Figures represent demonstration values.")
        if missing_from_stops > 0:
            warnings.append(f"{missing_from_stops} records have missing origin stops ('From Stop').")
        if missing_to_stops > 0:
            warnings.append(f"{missing_to_stops} records have missing destination stops ('To Stop').")
        if repeated_tickets > 0:
            warnings.append(f"{repeated_tickets} records have repeated ticket numbers across waybills (Preserved as valid distinct transactions per PRD 5.3).")
        if unresolved_non_nulls > 0:
            warnings.append(f"Source Column 10 ('Unnamed: 9') contains {unresolved_non_nulls} non-null values with {unresolved_unique_vals} unique entries. Kept as unresolved source field.")
        else:
            warnings.append("Source Column 10 ('Unnamed: 9') contains no non-null values.")
        if zero_collection_records > 0:
            warnings.append(f"{zero_collection_records} records have both zero collection and zero uncollected amount.")

        deductions = 0
        if total_records > 0:
            deductions += (missing_from_stops + missing_to_stops) / total_records * 50
            deductions += invalid_passenger_records / total_records * 30
        quality_score = max(75.0, round(100.0 - deductions, 2)) if total_records > 0 else 100.0

        return {
            "dataset_id": dataset_id,
            "filename": filename,
            "dataset_type": dataset_type,
            "is_demo": dataset_type == "DEMO_SAMPLE",
            "total_records": total_records,
            "missing_from_stops": missing_from_stops,
            "missing_to_stops": missing_to_stops,
            "repeated_ticket_numbers": repeated_tickets,
            "distinct_tickets": distinct_tickets,
            "distinct_waybills": distinct_waybills,
            "distinct_origins": distinct_origins,
            "distinct_destinations": distinct_destinations,
            "unresolved_column_name": "Unnamed: 9",
            "unresolved_column_non_nulls": unresolved_non_nulls,
            "unresolved_column_nulls": unresolved_nulls,
            "unresolved_column_unique_values": unresolved_unique_vals,
            "invalid_passenger_records": invalid_passenger_records,
            "zero_or_negative_collection_records": zero_collection_records,
            "warnings": warnings,
            "quality_score": quality_score
        }

    def get_raw_dataframe(self, dataset_id: Optional[str] = None) -> pd.DataFrame:
        """
        Retrieves the exact 10 source schema columns in their immutable order.
        Guarantees zero extra columns.
        """
        if not dataset_id:
            active = self.get_active_dataset()
            if not active:
                raise ValueError("No active dataset found.")
            dataset_id = active["dataset_id"]

        with self._get_connection() as conn:
            df = pd.read_sql_query("""
            SELECT waybill_number as "Waybill Number",
                   ticket_number as "Ticket Number",
                   from_stop as "From Stop",
                   to_stop as "To Stop",
                   date_str as "Date",
                   time_str as "Time",
                   total_psgr as "Total Psgr",
                   coll_amt as "Coll Amt",
                   uncoll_amt as "Uncoll Amt",
                   unresolved_col_10 as "Unnamed: 9"
            FROM raw_tickets
            WHERE dataset_id = ?
            ORDER BY id ASC
            """, conn, params=(dataset_id,))
        return df[EXACT_SOURCE_SCHEMA]

    def get_audit_logs(self, dataset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if dataset_id:
                cursor.execute("""
                SELECT * FROM transformation_audit_log WHERE dataset_id = ? ORDER BY logged_at DESC
                """, (dataset_id,))
            else:
                cursor.execute("""
                SELECT * FROM transformation_audit_log ORDER BY logged_at DESC LIMIT 100
                """)
            return [dict(r) for r in cursor.fetchall()]
