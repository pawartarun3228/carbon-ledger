# Carbon Ledger — Carbon Emission Monitoring and Net-Zero Recommendation Platform

> **“Measure emissions. Understand impact. Plan a lower-carbon future.”**  
> An institutional sustainability analytics platform for greenhouse gas emissions monitoring, verifiable factor accounting, leak-free machine learning forecasting, and net-zero scenario planning.  
> *Developed for University CSE / AIML Design Coursework Evaluation.*

---

## 1. Visual & Institutional Design Language

Carbon Ledger is built in an **editorial, institutional design style inspired by the visual language of the United Nations**:
- **Palette:** Deep UN Blue (`#004f98`), Deep Navy (`#0b2545`), Slate Gray (`#1e293b`), Restrained Teal (`#0d9488`), and Crisp Neutral Off-White (`#f8fafc`).
- **Typography & Structure:** Serif/sans pairing (Georgia & Inter), generous whitespace, strict tabular alignment, and zero gratuitous neon or glassmorphism.
- **Accessibility:** Semantic HTML5, visible `:focus-visible` keyboard states, WCAG contrast compliance, and ARIA attributes.
- **Legal & Governance Notice:** Independent academic prototype; does not use the UN emblem or imply official UN affiliation or regulatory audit assurance.

---

## 2. Core Application Modules

### A. Executive Sustainability Dashboard (`/dashboard`)
- **Total Emissions:** Dynamic calculations reported in both kilograms (kg CO₂e) and metric tonnes (t CO₂e).
- **Period Filter:** Custom monthly range filtering (`date_from` to `date_to`).
- **Breakdown Analytics:** Interactive Chart.js Doughnut chart and monthly timeline chart.
- **KPI Metrics:** Scope 2 electricity, Scope 1 fuel, Scope 3 commuter transit, primary emission driver with percentage share, and net-zero target progress.
- **Data Quality Alerts:** Real-time diagnostics flagging reporting gaps, small-sample forecasting warnings, and active demonstration data tags.
- **Audit Table:** Recent activity log with data source verification badges.

### B. Activity Data Management (`/history` / `/activities`)
- **Supported Categories & Units:**
  - Grid electricity: `kWh` / `MWh`
  - Liquid fuels: Motor gasoline / Petrol (`litre` / `gallon`) and Diesel (`litre` / `gallon`)
  - Public transit commuting: Transit bus and Passenger train (`passenger-km`, `pkm` = distance × passenger count)
  - Personal vehicle commuting: Passenger car (petrol/diesel) and Motorcycle (`vehicle-km`, `vkm` = distance driven)
- **CRUD Operations:** Create, view, edit (`/edit-data/<id>`), and delete records, with a one-click **Clear All** safeguard.
- **Bulk CSV Ingestion:** Drag-and-drop CSV upload with row-specific validation diagnostics.
- **Duplicate Warnings:** Detects potential duplicate entries within CSV batches and against existing database records.
- **AI Anomaly Quality Screening:** Integrated **Isolation Forest** flags uncharacteristic spikes or dips as **"Requires Audit Investigation"** with human-understandable explanations and verification guidance.

### C. Verifiable Emission Factor Registry (`/emission-factors`)
- **Equation:** Emissions (kg CO₂e) = Activity Quantity × Compatible Emission Factor.
- **Unit Safeguards:** Enforces unit compatibility and prevents unit mismatches and double counting.
- **Traceable Standards & Provenance:**
  - **Grid Electricity (Scope 2):** Central Electricity Authority (CEA) of India, *CO₂ Baseline Database for the Indian Power Sector, User Guide Version 19.0 (December 2023)*, Table 1: National Grid Weighted Average Gross Generation Emission Factor (including Renewable Energy Sources) for FY 2022-23 (0.716 kg CO₂e/kWh). Verified national grid average gross generation factor (not Combined Margin).
  - **Liquid Fuels (Scope 1):** IPCC 2006 Guidelines for National Greenhouse Gas Inventories, Vol 2 Energy, Ch 3 (2.31 kg/L petrol, 2.68 kg/L diesel).
  - **Passenger Mobility (Scope 3):** UK DEFRA / DESNZ 2023 GHG Conversion Factors per passenger-km (bus 0.089, train 0.041) and per vehicle-km (petrol car 0.192, diesel car 0.171, motorcycle 0.113).
- **Historical Reproducibility:** Calculations permanently persist the factor version, source, and exact numerical factor used at entry time.

### D. Machine Learning Forecasting Lab (`/forecasting`)
- **Research Rigor:** Strictly chronological rolling-window (expanding window) backtesting. Eliminates lookahead data leakage by training exclusively on past observations and predicting subsequent chronological folds.
- **Feature Engineering:** Backward-looking features only (lag 1, lag 2, 3-month rolling mean, trend index, and cyclical seasonal harmonics $\sin(2\pi m / 12), \cos(2\pi m / 12)$).
- **Multi-Model Benchmark:**
  1. *Naive Baseline:* Canonical zero-parameter persistence benchmark ($y_{t-1}$).
  2. *Linear Regression (Ridge):* L2-regularized linear model over trend, lags, and seasonal cyclical harmonics.
  3. *Random Forest Regressor:* Constrained depth ensemble (max_depth=3) capturing non-linear threshold effects.
- **Honest Metric Reporting:** Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), and R². Honest mathematical explanation for negative R² on short holdouts with low variance, resolved by rolling-window evaluation across annual cycles.
- **Dynamic Forward Projections:** Projects time-varying seasonal curves across the forward 3-month horizon rather than repeating a static flatline value.
- **Benchmark Toggle:** Switch between Local Inventory Records, 24-Month BDG2 Empirical Benchmark (`Bear_education_Maryjane`, 7,998.1 m² Higher Education building), and 24-Month Synthetic Validation Series.

### E. Explainable Recommendation Engine (`/recommendations`)
- **Deterministic & Evidence-Based:** Grounded in ISO 14064 principles and driven by the organization's verified carbon profile (never claimed as AI-generated).
- **Comprehensive Disclosures:**
  - Observed Evidence (e.g. "Electricity contributes 62.4% (1,240 kg CO2e) of verified emissions").
  - Causal Rationale (why the action is advised).
  - Estimated Abatement Potential (kg CO₂e and %).
  - Stated Engineering Assumptions.
  - Implementation Difficulty (Low / Medium / High).
  - Data Confidence Level (High / Moderate / Preliminary).
  - Actionable Milestones Checklist.
- **Trajectory Alert:** Flags month-over-month increases >5% with immediate operational audit steps.

### F. Net-Zero Scenario Planner (`/net-zero`)
- **Target Setting:** Configurable baseline emissions, target percentage (1–100%), and dynamic target year (2027–2070).
- **Activity-Level Simulation:** Real-time sliders for electricity, fuel, and transport reductions recalculate total emissions using real activity factors (not simple visual scaling).
- **Dynamic Trajectory Modeling:** Chart.js trajectory dynamically scales from current year to the saved target year (e.g. 2030, 2035, 2040, 2050), recalculating the simulated glide path in real time as sliders move.
- **Saved Scenarios:** Save and compare multiple decarbonization strategies.
- **5-Phase Implementation Roadmap:** Phased milestones from baseline auditing to residual carbon offset purchasing.

### G. Formal Reports, Data Exports & REST APIs (`/reports`)
- **PDF Report Generation:** Publication-grade ReportLab PDF with executive KPIs, category breakdowns, factor provenance, target progress, and audit disclaimers (`/reports/download-pdf`).
- **CSV Records Export:** Complete activity inventory with provenance fields (`/reports/download-csv`).
- **Monthly Summary Export:** Aggregated monthly totals by category (`/reports/download-monthly-csv`).
- **CSV Upload Template:** Standardized header and example rows for import (`/download-template`).
- **REST APIs:** Documented JSON endpoints for `/api/inventory-summary`, `/api/anomalies`, `/api/calculate`, and `/api/simulate-scenario`.

---

## 3. Technology Stack

| Layer | Component | Version / Specification |
| :--- | :--- | :--- |
| **Backend** | Python &amp; Flask | Python 3.12 / 3.14 compatible, Flask 3.1.3 |
| **Database** | SQLite3 | Parameterized SQL, zero-configuration local persistence |
| **Data Processing** | Pandas &amp; NumPy | Time-series rollups, lag engineering, array manipulations |
| **Machine Learning** | Scikit-learn | Ridge, RandomForestRegressor, IsolationForest, metrics |
| **PDF Generation** | ReportLab | Flowable document generation with institutional typography |
| **Frontend UI** | HTML5 / CSS3 / Vanilla JS | Bootstrap 5.3.3 + Custom UN-inspired CSS |
| **Data Visualizations** | Chart.js | Version 4.4.4 UMD (Doughnut, Line, Multi-series) |
| **Testing** | Pytest | 101 automated tests covering accounting, ML, AI, and APIs |

---

## 4. Datasets & Facility Scale Documentation

Carbon Ledger strictly documents three distinct datasets:

1. **Demonstration Activity Inventory (18 Months):**
   - **File:** `data/sample_activities.csv`
   - **Span:** 18 months (Jan 2023 &ndash; Jun 2024, 72 records).
   - **Facility Context:** Single university academic department facility (Department of Computer Science & Engineering, ~1,800 m², ~120 occupants, monthly electricity ~3,000–4,200 kWh).
2. **Empirical Benchmark Dataset (Building Data Genome 2, 24 Months):**
   - **File:** `data/bdg2_bear_education_maryjane.csv`
   - **Source:** Miller et al., *Scientific Data* 7, 368 (2020).
   - **Building ID:** `Bear_education_Maryjane` (7,998.1 m² Higher Education classroom & research building, 2016&ndash;2017 sub-metered electricity).
3. **Synthetic Benchmark Dataset (24 Months):**
   - **Source:** Algorithmic sinusoidal generator with trend and seasonal cycles for methodology verification.

---

## 5. Installation & Local Setup

### Prerequisites
- Windows OS (or Linux/macOS)
- Python 3.12, 3.13, or 3.14 installed

### Steps

1. **Navigate to the Project Directory**
   ```powershell
   cd C:\Users\VRtar\.gemini\antigravity\scratch\carbon-emission-platform
   ```

2. **Activate the Virtual Environment**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

3. **Install Dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Initialize Database and Launch Application**
   ```powershell
   python app.py
   ```
   The application will start locally at: **`http://127.0.0.1:5000`**

---

## 6. Automated Testing & Verification

Run the complete test suite (101 automated tests):
```powershell
.\venv\Scripts\python.exe -m pytest --rootdir="." tests/ -v
```

### Actual Test Execution Output:
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

## 7. Faculty Demonstration Guide

Follow this sequence to demonstrate all platform capabilities during an academic review:

1. **Landing Page (`/`):**
   - Present the UN-inspired institutional aesthetic, clear scope boundaries (Scopes 1, 2, and 3), and live summary chips.
2. **First Launch & Demonstration Data (`/dashboard`):**
   - Click **"Load Demo (18 Mo)"**. Point out that 18 months of academic department facility records (electricity, courier petrol, backup diesel, transit passes) are ingested.
   - Note the real-time calculations: Total kg CO₂e, metric tonnes, category doughnut chart, monthly trend, and data-quality banners.
3. **Activity Management & CSV Import (`/history`):**
   - Demonstrate the multi-dimensional filter bar (filter by category, date range, or data provenance).
   - Review the **AI Isolation Forest Anomaly Audit Review** banner showing flagged statistical deviations with human-understandable explanations.
   - Click **"CSV Template"** to inspect the import schema. Upload `data/sample_activities.csv` to showcase bulk ingestion with duplicate warnings.
4. **Factor Registry Traceability (`/emission-factors`):**
   - Show the Central Electricity Authority (CEA) v19 official baseline factor (0.716 kg/kWh, National Grid Weighted Average Gross Generation incl. RES for FY 2022-23) and IPCC 2006 fuel factors, emphasizing source provenance and version preservation.
5. **Machine Learning Forecasting Lab (`/forecasting`):**
   - Explain the danger of lookahead leakage and why random train/test splits are scientifically invalid for time-series.
   - Switch between **Inventory Records**, **BDG2 Empirical (24 Mo)**, and **Synthetic (24 Mo)**.
   - Review the chronological rolling-window backtesting table (Naive vs Ridge vs Random Forest) and the honest mathematical explanation for R².
   - Review the forward out-of-sample projection showing dynamic seasonal trajectory curves rather than flatline values.
6. **Explainable Recommendations (`/recommendations`):**
   - Show how recommendations dynamically respond to the dominant contributor (e.g. Grid Electricity at ~55-60%).
   - Review the causal rationale, estimated abatement potential, and explicit engineering assumptions.
7. **Net-Zero Scenario Planner (`/net-zero`):**
   - Set a target (e.g. 50% reduction by 2030, 2035, or 2040).
   - Adjust the **Electricity Abatement**, **Fuel**, and **Transport** sliders. Show how KPIs and the trajectory glide path dynamically update in real time.
   - Save the scenario ("Phase 1 Solar + Transit Pass") and view the 5-phase roadmap.
8. **Formal Report Download (`/reports`):**
   - Click **"Download Official PDF Report"** to open the ReportLab PDF document containing executive KPIs, factor registries, and audit disclaimers.
   - Download the CSV activity records and monthly summary exports.
9. **REST APIs & Documentation (`/api/inventory-summary`, `/methodology`):**
   - Open `/api/inventory-summary` to inspect the clean JSON API payload.
   - Conclude the walkthrough on the academic methodology documentation page reviewing formulas, system boundaries, and research limitations.

---

## 8. Repository Structure

```
carbon-emission-platform/
│
├── app.py                          # Flask application routing & API endpoints
├── requirements.txt                # Python package dependencies
├── pytest.ini                      # Pytest configuration
├── .env.example                    # Environment variable template
├── .gitignore                      # Git exclusion rules
├── README.md                       # Comprehensive documentation & evaluation guide
├── database.db                     # Local SQLite database
│
├── data/
│   ├── emission_factors.json       # Documented conversion factors catalog
│   ├── emission_factors.csv        # Tabular emission factors export
│   ├── sample_activities.csv       # 18-month academic department sample dataset
│   └── bdg2_bear_education_maryjane.csv # 24-month Building Data Genome 2 empirical dataset
│
├── models/
│   ├── __init__.py
│   ├── database.py                 # SQLite persistence, schema, and queries
│   └── saved_models/               # Serialized forecaster artifacts (.joblib)
│
├── services/
│   ├── __init__.py
│   ├── emission_calculator.py      # Core CO2e calculation & unit checking
│   ├── factor_registry.py          # Factor catalog & unit conversions
│   ├── data_validation.py          # Activity entry & CSV validation
│   ├── aggregation.py              # Multi-dimensional analytics & audits
│   ├── forecasting.py              # ML leak-free time-series experiments
│   ├── anomaly_detector.py         # AI Isolation Forest Quality Screening
│   ├── prediction.py               # Single-step trend projections
│   ├── recommendation_engine.py    # Evidence-based explainable advisory
│   ├── scenario_engine.py          # Activity-based net-zero simulator
│   └── report_generator.py         # ReportLab PDF & CSV exports
│
├── templates/
│   ├── base.html                   # UN-inspired institutional base layout
│   ├── index.html                  # Landing page with core pillars
│   ├── dashboard.html              # Executive analytics dashboard
│   ├── history.html                # Activity management, CSV upload & AI anomaly review
│   ├── add_data.html               # Single activity logging form with unit guidance
│   ├── edit_data.html              # Activity modification form
│   ├── emission_factors.html       # Transparent factor registry view
│   ├── prediction.html             # ML Forecasting Lab & benchmark switcher
│   ├── recommendations.html        # Prioritized decarbonization advice
│   ├── net_zero.html               # Net-Zero scenario simulator & roadmap
│   ├── reports.html                # Reporting center & export downloads
│   └── methodology.html            # Research methodology & architecture
│
├── static/
│   ├── css/
│   │   └── style.css               # UN institutional editorial stylesheet
│   └── js/
│       └── dashboard.js            # Chart.js & interactive simulation logic
│
├── docs/
│   ├── methodology.md              # Environmental accounting methodology
│   ├── architecture.md             # System architecture & database schema
│   ├── testing.md                  # Test execution report (101 tests)
│   └── research_report.md          # AIML time-series forecasting research
│
└── tests/
    ├── test_app.py                 # Baseline test suite (43 tests)
    └── test_platform_features.py   # Advanced platform features suite (58 tests)
```
