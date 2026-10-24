# Carbon Ledger: Scientific & Environmental Accounting Methodology

## 1. Executive Summary & Research Objectives

Carbon Ledger is a software platform designed to monitor organizational greenhouse gas (GHG) emissions, maintain verifiable emission factor provenance, perform leak-free machine learning forecasting, generate evidence-backed decarbonization recommendations, and simulate net-zero scenario glide paths.

The primary objective of this platform is to bridge deterministic environmental accounting standards with empirical data science and policy modeling within an accessible, transparent, and reproducible software prototype.

---

## 2. Fundamental Distinction: Accounting vs. Machine Learning

A foundational principle of Carbon Ledger is the strict separation between **deterministic greenhouse gas accounting** and **probabilistic machine learning forecasting**:

| Dimension | Carbon Accounting Engine | ML Forecasting Lab |
| :--- | :--- | :--- |
| **Scientific Paradigm** | Deterministic, physics-based stoichiometric inventory | Empirical statistical / non-linear pattern extrapolation |
| **Governing Formulation** | Emissions = Σ (Activity × Factor) | ŷ<sub>t</sub> = f(trend<sub>t</sub>, y<sub>t-1</sub>, y<sub>t-2</sub>, ȳ<sub>3</sub>, sin<sub>m</sub>, cos<sub>m</sub>) |
| **Operational Role** | Regulatory compliance, baseline setting, audited disclosure | Internal budgetary projections, scenario exploration |
| **Error Tolerance** | Zero tolerance: Rejects non-finite, missing, or negative values | Evaluated via chronological rolling-window residuals (MAE, RMSE, R²) |
| **Data Requirements** | Discrete utility bills, fuel receipts, transit logs | Chronological monthly time-series (T >= 5 months) |

---

## 3. Dataset Provenance & Facility Scale Clarification

To ensure scientific integrity and eliminate ambiguity regarding facility scale, Carbon Ledger documents three distinct datasets:

1. **Demonstration Activity Inventory (18 Months):**
   - **File:** `data/sample_activities.csv`
   - **Date Range:** January 2023 through June 2024 (18 months, 72 discrete records).
   - **Facility Context:** Representative of a single university academic department facility (Department of Computer Science & Engineering, ~1,800 m² gross floor space, ~120 occupants).
   - **Consumption Profile:** Monthly grid electricity ~3,000–4,200 kWh; shuttle/fleet fuel ~340–440 litres petrol and ~150–220 litres diesel; commuting ~3,800–4,500 passenger-km bus and ~1,100–1,400 vehicle-km cars.
   - **Purpose:** Onboarding and functional verification of accounting, reporting, and activity editing modules. *It does not claim to represent an entire 20,000-student university campus.*

2. **Empirical Benchmark Dataset (Building Data Genome 2, 24 Months):**
   - **File:** `data/bdg2_bear_education_maryjane.csv`
   - **Source:** Miller et al., *"The Building Data Genome 2 Project: An open, comprehensive data set from 3,053 energy meters"*, Scientific Data 7, 368 (2020).
   - **Building ID:** `Bear_education_Maryjane` (Site: Bear, University Campus).
   - **Primary Space Usage:** Higher Education (Classrooms, research laboratories, faculty offices).
   - **Gross Floor Area:** 7,998.1 m² (86,091 sq ft), built in 1964.
   - **Observations:** 24 continuous calendar months (January 2016 – December 2017), aggregated from 17,520 hourly electricity sub-meter readings (~197,000 to 295,000 kWh/month).
   - **Purpose:** Rigorous empirical machine-learning forecasting benchmark across a full two-year operational horizon.

3. **Synthetic Validation Benchmark (24 Months):**
   - **Generator:** `services.forecasting.generate_synthetic_benchmark_dataset()`
   - **Profile:** 24 months of synthetic seasonal sinusoidal variation (summer cooling peaks, winter heating) plus secular trend and Gaussian noise.
   - **Purpose:** Synthetic mathematical verification to test algorithm stability under known data-generating processes.

---

## 4. System Boundaries & GHG Protocol Scopes

Carbon Ledger implements standard corporate inventory boundaries under the **World Resources Institute (WRI) / World Business Council for Sustainable Development (WBCSD) GHG Protocol Corporate Standard**:

```
+-----------------------------------------------------------------------------------+
|                        ORGANIZATIONAL CARBON BOUNDARY                             |
+-----------------------------------------------------------------------------------+
| Scope 1: Direct Combustion                                                        |
|   - Mobile Combustion: Department courier & passenger petrol fleet (litres)       |
|   - Stationary Combustion: Emergency backup diesel generators (litres)            |
+-----------------------------------------------------------------------------------+
| Scope 2: Indirect Purchased Energy                                                |
|   - Grid Electricity: Academic halls, lighting, computing, and HVAC (kWh)         |
+-----------------------------------------------------------------------------------+
| Scope 3: Upstream & Commuting Mobility                                            |
|   - Category 7 (Employee Commuting): Public transit bus & rail (passenger-km)     |
|   - Personal Vehicles: Passenger cars & motorcycles (vehicle-km)                  |
+-----------------------------------------------------------------------------------+
```

---

## 5. Mathematical Formulations

### 5.1. Carbon Emission Equation
For each individual activity entry k occurring in reporting period t:

$$\text{CO}_2\text{e}_{k} = Q_{k} \times EF_{\text{compatible}}(c_k)$$

Where:
- $Q_k$ is the normalized activity quantity (e.g. kWh, litres, passenger-km, vehicle-km).
- $EF(c_k)$ is the approved conversion factor for category $c_k$ in compatible units (kg CO₂e/unit).
- Total inventory for reporting interval T is the exact sum:
  $$\text{Total CO}_2\text{e} = \sum_{k \in T} \text{CO}_2\text{e}_k$$

Conversion to metric tonnes ($\text{t CO}_2\text{e}$):
$$\text{Tonnes CO}_2\text{e} = \frac{\text{Emissions (kg CO}_2\text{e})}{1000}$$

### 5.2. Net-Zero Target Formulation
For a designated historical baseline emission $E_{\text{baseline}}$ and declared reduction commitment fraction $R \in (0, 1]$ targeting year $Y_{\text{target}}$:

$$\text{Target Allowance} = E_{\text{baseline}} \times (1 - R)$$
$$\text{Required Abatement} = E_{\text{baseline}} \times R$$

Annual linear reduction glide path from current year $Y_{\text{current}}$ to target year $Y_{\text{target}}$:
$$\Delta E_{\text{annual}} = \frac{E_{\text{baseline}} \times R}{Y_{\text{target}} - Y_{\text{current}}}$$

### 5.3. Activity-Based Scenario Recalculation
Decarbonization scenarios simulate physical activity interventions across individual categories:

$$E_{\text{scenario}} = E_{\text{elec}} \times (1 - r_{\text{elec}}) + E_{\text{fuel}} \times (1 - r_{\text{fuel}}) + E_{\text{trans}} \times (1 - r_{\text{trans}}) + E_{\text{other}}$$

Remaining target gap:
$$\text{Gap} = \max\left(0, E_{\text{scenario}} - \text{Target Allowance}\right)$$

---

## 6. Approved Emission Factor Registry & Verified Provenance

All factors in the system catalog are documented and traceable:

1. **Grid Electricity (Scope 2):**
   - **Source:** Central Electricity Authority (CEA), Ministry of Power, Government of India: *CO₂ Baseline Database for the Indian Power Sector, User Guide Version 19.0 (December 2023)*, Table 1.
   - **Baseline Factor:** 0.716 kg CO₂e/kWh (0.716 t CO₂/MWh).
   - **Verified Definition:** National Grid Weighted Average Gross Generation Emission Factor (including Renewable Energy Sources) for Fiscal Year 2022-23.
   - **Provenance Note:** This is the national grid weighted average gross generation baseline, *not* the Combined Margin (CM ~0.76–0.79 t CO₂/MWh) or Operating Margin.

2. **Motor Gasoline / Petrol (Scope 1):**
   - **Source:** Intergovernmental Panel on Climate Change (IPCC): *2006 Guidelines for National Greenhouse Gas Inventories, Volume 2 (Energy), Chapter 3 (Mobile Combustion)*.
   - **Baseline Factor:** 2.31 kg CO₂e/litre.
   - **Boundary:** Direct tank-to-wheel stoichiometric combustion.

3. **Gas / Diesel Oil (Scope 1):**
   - **Source:** IPCC 2006 Guidelines, Volume 2 (Energy), Chapter 3.
   - **Baseline Factor:** 2.68 kg CO₂e/litre.
   - **Boundary:** Direct generator and transport combustion.

4. **Transportation Units (Scope 3):**
   - **Source:** UK Department for Energy Security and Net Zero (DESNZ) / DEFRA: *Government Greenhouse Gas Conversion Factors for Company Reporting (2023)*.
   - **Public Transit Bus:** 0.089 kg CO₂e/passenger-km (pkm = distance × passenger count).
   - **National Rail Transit:** 0.041 kg CO₂e/passenger-km (pkm).
   - **Passenger Car (Petrol):** 0.192 kg CO₂e/vehicle-km (vkm = vehicle distance driven).
   - **Passenger Car (Diesel):** 0.171 kg CO₂e/vehicle-km (vkm).
   - **Motorcycle / Two-Wheeler:** 0.113 kg CO₂e/vehicle-km (vkm).

---

## 7. Machine Learning Forecasting Methodology & Leakage Prevention

### 7.1. Chronological Rolling-Window Backtesting
To prevent *lookahead leakage* (where models inadvertently learn from future data to predict the past), Carbon Ledger implements chronological expanding-window backtesting:
- For evaluation horizon $t \in [t_{\text{start}}, N-1]$, models are trained exclusively on observations $1 \dots t-1$ and evaluated on month $t$.
- All candidates (Naive Baseline, Ridge Linear Regression, Random Forest Regressor) are evaluated across the exact same chronological test folds.

### 7.2. Why Naive Baseline Prevailed and Negative R² Occurred
- **Overfitting on Tiny Samples:** On short time series (e.g., N = 18 with 3-point holdouts), fitting multi-parameter models causes severe parameter estimation variance. The zero-parameter Naive persistence model ($\hat{y}_t = y_{t-1}$) introduces zero estimation variance and often achieves lower RMSE on small samples.
- **Holdout Variance Artifact:** The coefficient of determination is defined as:
  $$R^2 = 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y}_{\text{test}})^2}$$
  When the test holdout spans only 3 months, the test sample variance $\text{TSS} = \sum (y_i - \bar{y})^2$ is tiny. If the model's residual error $\text{RSS}$ exceeds this small variance, $R^2$ becomes negative.
- **The Solution:** Evaluating over a 12-month rolling window across an annual operational cycle captures true seasonal variance, producing positive $R^2$ values (up to ~0.49 on the BDG2 benchmark).

---

## 8. AI Anomaly Quality Screening (Isolation Forest)

Carbon Ledger integrates an unsupervised **Isolation Forest** (`services.anomaly_detector`) to assist human auditors in identifying statistical irregularities:
- **Features Analyzed:** Category-relative activity ratios ($Q_i / \text{median}(Q_{\text{cat}})$), category z-scores, log consumption, and total emissions.
- **Classification:** Flagged entries are designated strictly as **"Requires Audit Investigation"** with clear explanations and auditor follow-up suggestions (e.g. multi-month consolidated billing, meter multiplier discrepancies, or seasonal HVAC peaks). They are never flagged as confirmed errors.
