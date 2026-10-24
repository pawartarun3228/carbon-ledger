# Carbon Ledger: Verification & Testing Report

## 1. Automated Testing Framework

Carbon Ledger is validated by an extensive suite of automated tests implemented in `pytest`. 
All tests execute in isolated, self-cleaning temporary SQLite database instances.

Command to run full suite:
```powershell
.\venv\Scripts\pytest --rootdir="." tests/ -v
```

---

## 2. Test Execution Summary

```
============================= test session starts =============================
platform win32 -- Python 3.14.2, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\VRtar\.gemini\antigravity\scratch\carbon-emission-platform
configfile: pytest.ini
collected 101 items

tests\test_app.py ...........................................            [ 42%]
tests\test_platform_features.py ........................................ [ 82%]
..................                                                       [100%]

============================= 101 passed in 7.32s =============================
```

---

## 3. Test Coverage Breakdown

### 3.1. Baseline Suite (`tests/test_app.py` - 43 Tests)
- **Emission Calculations (7 tests):** Electricity, petrol, diesel, passenger vehicle calculations; zero and negative rejection; invalid category handling; category listing.
- **Database Persistence (5 tests):** Schema initialization, user creation, emission record insertion, record deletion, category-filtered retrieval.
- **Recommendations Engine (5 tests):** Empty dataset handling, electricity-dominant ranking, transportation-dominant ranking, tip population, impact thresholds.
- **Net-Zero Planning (6 tests):** Target formula computation, 100% reduction handling, progress percentage derivation, invalid baseline rejection, 5-phase roadmap.
- **Single-Step Trend Prediction (4 tests):** Insufficient data threshold (< 4 months), sufficient data regression prediction, R² extraction, empty set handling.
- **Flask Routes & JSON APIs (16 tests):** Status 200 on all primary routes, POST form submissions, JSON API formats, demo data loading and clearing.

### 3.2. Platform Features Suite (`tests/test_platform_features.py` - 58 Tests)
- **Calculation Precision & Units (5 tests):** Verified benchmarks for CEA electricity, IPCC petrol/diesel, DEFRA transit; kg to metric tonnes exact conversions.
- **Input Rejection & Data Validation (6 tests):** Rejection of zero, negative, `NaN`, `+Inf`, `None`, and unregistered categories.
- **Unit Compatibility & Normalization (5 tests):** Rejection of incompatible units; conversion of alternate units (MWh to kWh, miles to km, passenger-miles to passenger-km).
- **Factor Provenance (3 tests):** Verification of CEA India, IPCC, and DEFRA metadata tags, source URLs, and version identifiers.
- **CSV Import & Row-Level Diagnostics (4 tests):** Correct parsing, missing column rejection, row-specific error reporting, in-batch duplicate warnings.
- **Database Persistence (2 tests):** Scenarios CRUD lifecycle and forecast experiment recording.
- **Scenario Simulation & Multiple Target Years (4 tests):** Activity-level category reduction recalculation, target gap tracking, trajectory generation across multiple target years (2030, 2035, 2040, 2050) and reduction percentages (10% to 100%).
- **Machine Learning & Leakage Safeguards (5 tests):** Chronological ordering verification, lag feature leakage prevention, multi-model evaluation (Naive, Ridge, Random Forest), BDG2 empirical benchmark loading, and dynamic multi-step out-of-sample forward projections.
- **AI Anomaly Quality Screening (3 tests):** Isolation Forest screening, insufficient data safeguards, uncharacteristic spike detection with explainable audit guidance, and graceful handling of missing or invalid data.
- **Report Generation (4 tests):** ReportLab PDF rendering with magic bytes check (`%PDF`), CSV records export, CSV monthly export, CSV template download.
- **Extended HTTP & API Integration (17 tests):** `/activities`, `/emission-factors`, `/forecasting`, `/forecasting?benchmark=synthetic`, `/forecasting?benchmark=bdg2`, `/reports`, `/reports/download-pdf`, `/reports/download-csv`, `/reports/download-monthly-csv`, `/download-template`, `/methodology`, `/upload-csv`, `/api/simulate-scenario`, `/api/inventory-summary`, `/api/anomalies`, `/clear-all-data`.

---

## 4. Verification Checklists Passed
- [x] Zero hardcoded statistics on dashboard.
- [x] All figures derived from database and calculation engine.
- [x] Strictly chronological rolling-window backtesting without future-data leakage.
- [x] Activity-based scenario recalculation using underlying factors.
- [x] Dynamic net-zero glide path trajectory matching user-selected target year.
- [x] Verified CEA electricity factor provenance (FY 2022-23 National Grid Weighted Average Gross Generation incl. RES).
- [x] Clear transportation unit separation (passenger-km vs vehicle-km).
- [x] Honest mathematical explanation for negative R² on short holdouts.
- [x] AI Isolation Forest quality screening with explainable audit recommendations.
- [x] Production of valid, styled PDF documents without crashing.
- [x] Rejection of negative, infinite, and zero consumption values.
