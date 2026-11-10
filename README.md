# SmartBus: Karnataka Intelligent Bus Transport Analytics Platform
**SOLVATHON 2026 – Problem Statement 3** | Version 1.1 (Audited & Stabilized)

SmartBus is a government-grade intelligent transit analytics platform that converts raw daily bus ticket transaction logs into verified operational intelligence for transport department officials.

---

## Non-Negotiable 10-Column Source Schema

Every supported dataset (Excel or CSV) must follow **strictly and without exception** the exact 10 columns in this exact sequence:

1. `Waybill Number`
2. `Ticket Number`
3. `From Stop`
4. `To Stop`
5. `Date`
6. `Time`
7. `Total Psgr`
8. `Coll Amt`
9. `Uncoll Amt`
10. `Unnamed: 9`

### Immutability & Schema Rules
- **No 11th Column**: Uploads with extra columns are rejected with a clear descriptive error.
- **Exact Sequence**: Column reordering or missing columns are rejected automatically.
- **No In-Place Modifications**: Original uploaded files on disk remain byte-for-byte unchanged.
- **Source Export**: The `/api/export/source-data-csv` endpoint exports strictly the verified 10 columns in original order.
- **Separate Analytical Calculations**: All KPIs, percentiles, dynamic peaks, and anomalies are stored separately in analytical response objects and database views, never written back to the source dataset.

---

## Key Capabilities & Functional Coverage

| Module | PRD Requirement | Description |
|---|---|---|
| **Executive Overview** | FR-03 | Centralized summary of 8 core KPIs dynamically computed from the active dataset. Strictly ensures passenger sums are never mislabeled as unique passengers. |
| **Dataset Management & Quality Audit** | FR-01, FR-02 | Strict schema validation, multi-dataset repository with one-click dataset switcher, distinction between `Demo/Benchmark` data and `Department Upload`, and transformation audit trails. |
| **Passenger & Ticket Analytics** | FR-04 | Distribution of passenger count per ticket, top origin terminals, top destination stops, and ticket-to-passenger volume ratios. |
| **Collection Analytics** | FR-05 | Reconciles realized collection (`Coll Amt`) and recorded uncollected amounts (`Uncoll Amt`), with waybill collection rankings. |
| **Origin–Destination (OD) Intelligence** | FR-06 | Identifies high-demand transit movements, low-volume pairs, and terminal passenger net flow (departures vs arrivals) without manufactured route IDs. |
| **Time-Based Analytics** | FR-07 | 24-hour transaction and passenger trends with **dynamically detected peak operating windows** derived from actual load curves. |
| **Waybill Analytics** | FR-08 | Fleet waybill activity metrics, active operating hours, and average collection per ticket without unsubstantiated vehicle or driver claims. |
| **Automated Insights Engine** | FR-09 | Structured, explainable narrative findings with supporting metrics, baselines, and explicit limitations dynamically scoped to active dataset dates. |
| **Anomaly Detection Engine** | FR-10 | Dual-layer detection distinguishing Data-Quality anomalies from Operational Statistical anomalies using IQR (1.5x) and Modified Z-Score (MAD). |
| **Forecasting Engine** | FR-11 | Strict Product Governance enforcement locking multi-day predictions when historical days < 7; includes an evaluator simulation preview clearly marked as synthetic. |
| **Actionable Recommendations** | FR-12 | Practical operational guidance with supporting evidence, prerequisites, and impact ratings. |
| **Ask SmartBus (Conversational AI)** | FR-13 | Natural-language query interface with zero hallucinated figures, dynamically reflecting the currently selected dataset. |
| **Exports & Reporting** | Sec 6, 8 | Official PDF Executive Briefing, Verified Source Data CSV (exact 10 columns), and analytical summary CSVs. |

---

## Technology Stack & Environment Design

- **Backend**: FastAPI (Python 3.13), SQLite (transactional relational engine), NumPy, Pandas, PyArrow, ReportLab.
- **Frontend**: Karnataka State Transport executive portal, HTML5 / Tailwind CSS, Chart.js, Lucide Icons (fully self-contained, zero Node/npm build failures).
- **Zero-Network In-Process Storage**: Operates entirely within offline / sandboxed environments using Python's native high-performance data libraries without external database daemons or network dependencies.

---

## Quickstart Guide

### 1. Launch the Application
```bash
python run_app.py
```
Open your browser to :
- **Interactive Government Dashboard**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Run the Verification Suite
```bash
python -m pytest tests/ -v
```
All **29 test cases** verify exact 10-column schema order enforcement, extra column rejection, file preservation, multi-dataset isolation, dynamic peak detection, anomaly bounds, and conversational query grounding.
