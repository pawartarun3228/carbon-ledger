# Carbon Ledger: System Architecture & Data Engineering

## 1. Architectural Philosophy

Carbon Ledger is designed as a **clean, modular monolithic web application** prioritizing maintainability, data integrity, testability, and operational transparency. It avoids unnecessary distributed microservices, third-party cloud lock-in, and paid external API dependencies.

---

## 2. Layered Component Diagram

```
+-----------------------------------------------------------------------------------+
|                           PRESENTATION LAYER (HTML5 / CSS / JS)                   |
|  - Bootstrap 5.3 + Custom UN-Inspired Editorial Design System                     |
|  - Chart.js 4.x Interactive Visualizations                                        |
|  - Accessible Semantic Markup & Tabular Reporting UI                              |
+-----------------------------------------------------------------------------------+
                                        |  HTTP / REST JSON
                                        v
+-----------------------------------------------------------------------------------+
|                        APPLICATION ROUTING LAYER (Flask 3.1)                      |
|  - Page Controllers: /dashboard, /history, /forecasting, /net-zero, /reports      |
|  - API Endpoints: /api/inventory-summary, /api/anomalies, /api/calculate, ...    |
|  - File Download Streaming: /reports/download-pdf, /reports/download-csv          |
+-----------------------------------------------------------------------------------+
                                        |  Service Invocation
                                        v
+-----------------------------------------------------------------------------------+
|                             BUSINESS SERVICE LAYER                                |
|  +--------------------------------+  +-----------------------------------------+  |
|  | services/emission_calculator   |  | services/factor_registry                |  |
|  | - Unit compatibility & bounds  |  | - Provenance metadata & conversions     |  |
|  +--------------------------------+  +-----------------------------------------+  |
|  +--------------------------------+  +-----------------------------------------+  |
|  | services/data_validation       |  | services/aggregation                    |  |
|  | - CSV schema & row errors      |  | - Multi-dimensional rollups & audits    |  |
|  +--------------------------------+  +-----------------------------------------+  |
|  +--------------------------------+  +-----------------------------------------+  |
|  | services/forecasting (ML)      |  | services/anomaly_detector (AI)          |  |
|  | - Rolling-window backtesting   |  | - Isolation Forest Quality Screening    |  |
|  +--------------------------------+  +-----------------------------------------+  |
|  +--------------------------------+  +-----------------------------------------+  |
|  | services/scenario_engine       |  | services/recommendation_engine          |  |
|  | - Dynamic annual glide paths   |  | - Deterministic ISO 14064 heuristics    |  |
|  +--------------------------------+  +-----------------------------------------+  |
+-----------------------------------------------------------------------------------+
                                        |  SQL Queries & ORM / Raw DB API
                                        v
+-----------------------------------------------------------------------------------+
|                        PERSISTENCE LAYER (SQLite3 / database.db)                  |
|  - users: User credentials and organizational identity                            |
|  - emission_records: Historical activities, provenance, and calculated CO2e      |
|  - emission_factors: Standard factor registry table                               |
|  - net_zero_targets: Declared reduction commitments & baseline                    |
|  - scenarios: Saved activity-reduction simulation models                          |
|  - forecast_experiments: Experiment evaluation runs (MAE, RMSE, R2, best model)   |
+-----------------------------------------------------------------------------------+
```

---

## 3. Database Schema

The SQLite schema preserves foreign keys, timestamps, and full factor provenance:

```sql
-- Activity Records with Provenance Tracking
CREATE TABLE emission_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT 1,
    date TEXT NOT NULL,                  -- YYYY-MM or YYYY-MM-DD
    category TEXT NOT NULL,              -- e.g. electricity, petrol, diesel, transport_bus
    activity REAL NOT NULL,              -- consumption quantity
    unit TEXT NOT NULL,                  -- e.g. kWh, litre, passenger-km, vehicle-km
    emission_factor REAL NOT NULL,       -- applied conversion factor
    co2e REAL NOT NULL,                  -- calculated kg CO2e
    data_source TEXT DEFAULT 'Manual Entry',
    notes TEXT DEFAULT '',
    factor_source TEXT DEFAULT '',       -- traceable standard
    factor_version TEXT DEFAULT '',      -- standard version applied
    is_demo INTEGER DEFAULT 0,           -- 1 = synthetic demo, 0 = measured
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Active Decarbonization Targets
CREATE TABLE net_zero_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT 1,
    baseline_emission REAL NOT NULL,
    target_emission REAL NOT NULL,
    target_reduction_percentage REAL NOT NULL,
    target_year INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Saved Net-Zero Scenarios
CREATE TABLE scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT 1,
    name TEXT NOT NULL,
    target_year INTEGER NOT NULL,
    electricity_reduction_pct REAL NOT NULL DEFAULT 0.0,
    fuel_reduction_pct REAL NOT NULL DEFAULT 0.0,
    transport_reduction_pct REAL NOT NULL DEFAULT 0.0,
    baseline_co2e REAL NOT NULL,
    scenario_co2e REAL NOT NULL,
    annual_savings_co2e REAL NOT NULL,
    target_gap_co2e REAL NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Machine Learning Experiment Runs
CREATE TABLE forecast_experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dataset_type TEXT DEFAULT 'Historical Records',
    data_points INTEGER NOT NULL,
    train_points INTEGER NOT NULL,
    test_points INTEGER NOT NULL,
    split_cutoff TEXT NOT NULL,
    model_name TEXT NOT NULL,
    features TEXT NOT NULL,
    mae REAL NOT NULL,
    rmse REAL NOT NULL,
    r2 REAL,
    is_best INTEGER DEFAULT 0,
    evaluation_criterion TEXT DEFAULT 'Lowest RMSE',
    notes TEXT
);
```

---

## 4. Documented JSON API Reference

All JSON endpoints return standard HTTP status codes (`200 OK`, `400 Bad Request`, `404 Not Found`).

### 4.1. Inventory Summary Endpoint
- **URL:** `GET /api/inventory-summary`
- **Description:** Returns executive summary of organizational emissions, period count, scope breakdown, net-zero commitment status, and quality flags.
- **Response Schema:**
```json
{
  "total_records": 72,
  "total_emissions_kg": 79840.45,
  "total_emissions_tonnes": 79.8405,
  "period_months": 18,
  "highest_emitting_category": "Grid Electricity",
  "scopes": {
    "scope_1_kg": 29840.10,
    "scope_2_kg": 43500.25,
    "scope_3_kg": 6500.10
  },
  "has_net_zero_target": true,
  "target_summary": {
    "target_year": 2030,
    "target_reduction_pct": 50.0,
    "baseline_emission_kg": 80000.0,
    "target_allowance_kg": 40000.0
  },
  "audit_anomalies_flagged": 2
}
```

### 4.2. Emission Calculation Endpoint
- **URL:** `POST /api/calculate`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "category": "electricity",
  "activity": 1250.5,
  "unit": "kWh"
}
```
- **Response Schema:**
```json
{
  "category": "electricity",
  "category_name": "Grid Electricity (Indian National Grid Average)",
  "activity": 1250.5,
  "unit": "kWh",
  "calc_unit": "kWh",
  "emission_factor": 0.716,
  "factor_unit": "kg CO2e/kWh",
  "co2e": 895.358,
  "co2e_tonnes": 0.8954,
  "scope": "Scope 2",
  "source": "CEA CO2 Baseline Database for the Indian Power Sector, User Guide Version 19.0 (Dec 2023), Table 1",
  "version": "v19.0 (Verified Official)",
  "region": "India (national grid weighted average)"
}
```

### 4.3. AI Quality Screening / Anomaly Detection Endpoint
- **URL:** `GET /api/anomalies`
- **Description:** Runs Scikit-learn's Isolation Forest on historical records, standardizing by category median and z-score to identify statistical spikes or dips.
- **Response Schema:**
```json
{
  "has_sufficient_data": true,
  "total_inspected": 72,
  "anomalies_flagged": 2,
  "flagged_records": [
    {
      "record_id": 91,
      "date": "2023-09",
      "category": "transport_bus",
      "activity": 4400.0,
      "unit": "passenger-km",
      "flag_type": "Uncharacteristic High Spike",
      "explanation": "Reported 4,400.0 passenger-km is 1.1x the historical category median (4,020.0 passenger-km).",
      "recommended_action": "Verify trip log for multi-event consolidated accounting.",
      "audit_status": "Requires Audit Investigation"
    }
  ],
  "algorithm": "Isolation Forest (Scikit-Learn Ensemble)"
}
```

### 4.4. Decarbonization Scenario Simulation Endpoint
- **URL:** `POST /api/simulate-scenario`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "base_dict": {
    "electricity": 42000.0,
    "fuel": 24000.0,
    "transportation": 14000.0,
    "other": 0.0
  },
  "target_pct": 50.0,
  "target_year": 2030,
  "elec_reduction": 20.0,
  "fuel_reduction": 15.0,
  "transport_reduction": 15.0
}
```
- **Response:** Recalculated scenario emissions, savings, remaining gap, and year-by-year trajectory pathway.

---

## 5. Security & Data Integrity Protections

1. **SQL Injection Prevention:** All database queries utilize parameterized queries (`?` placeholders).
2. **Missing & Negative Values:** Activity values <= 0, `NaN`, and `Infinity` are rejected with descriptive HTTP 400 / flash messages.
3. **Data Loss Safeguards:** `clear_demo_data()` targets strictly `is_demo = 1` rows, guaranteeing custom user entries are never erased. The `clear_all_data()` action requires explicit user confirmation.
4. **Historical Provenance:** Calculations store the exact numerical factor and version at the time of entry, ensuring reports remain reproducible even if global factor catalogs update.
