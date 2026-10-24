# Carbon Ledger: Machine Learning Research & Forecasting Report

**Coursework Project:** B.Tech / University CSE / AIML Design Coursework  
**Module:** Empirical Machine Learning for Environmental Analytics  
**System:** Carbon Ledger &mdash; Multi-Model Time Series Forecasting Lab  

---

## 1. Research Problem & Motivation

Forecasting organizational greenhouse gas (GHG) emissions is vital for setting realistic interim net-zero targets and anticipating regulatory compliance costs. However, applied machine learning in environmental accounting faces severe methodological pitfalls:

1. **Catastrophic Lookahead Leakage:** Standard machine learning workflows frequently apply random k-fold cross-validation or random `train_test_split`. In time-series domains, random shuffling causes models to learn from future observations to predict the past, producing severely inflated, artificial accuracy.
2. **Small-Sample Variance:** Real organizations typically compile emission inventories at monthly resolution, yielding only 12–36 data points. Deep architectures (LSTMs, Transformers) overfit catastrophically on such regimes.
3. **Deterministic vs Stochastic Conflation:** Lay implementations confuse carbon accounting (a deterministic multiplication Q × EF) with machine learning (inductive statistical modeling).
4. **The "Flatline Forecast" and Negative R² Traps:** Naive multi-step persistence loops and unrepresentative 3-point holdouts often produce negative R² metrics and identical static predictions.

---

## 2. Experimental Design & Leakage Prevention Protocol

To address these challenges, Carbon Ledger implements chronological expanding-window (rolling-window) backtesting:

```
Chronological Rolling-Window Backtesting:
Fold 1:  [ Month 1 ... Month t-1 ]  -->  Predict Month t
Fold 2:  [ Month 1 ... Month t   ]  -->  Predict Month t+1
...
Fold K:  [ Month 1 ... Month N-1 ]  -->  Predict Month N
```

### 2.1. Feature Engineering
Features are constructed strictly using backward-looking windows ($t-1, t-2$) and cyclical calendar harmonics:
- **Trend Index ($t$):** Chronological integer index ($1, 2, \dots, T$) capturing secular operational expansion or efficiency shifts.
- **$\text{Lag}_1$ ($y_{t-1}$):** Emission level of the immediate prior month.
- **$\text{Lag}_2$ ($y_{t-2}$):** Emission level from two months prior.
- **Rolling Mean ($\bar{y}_{3}$):** Mean of the past three historical observations.
- **Cyclical Calendar Harmonics:** $\sin(2\pi m / 12)$ and $\cos(2\pi m / 12)$ where $m \in [1, 12]$ is the calendar month, capturing seasonal heating/cooling demand without lookahead bias.

---

## 3. Candidate Model Formulations

Three candidate architectures are evaluated across the identical chronological test folds:

### Model 1: Naive Persistence Baseline
Assumes next month's emissions will mirror the current month:
$$\hat{y}_{t} = y_{t-1}$$
*Role:* Essential baseline. Any viable predictive model must demonstrate superiority over this zero-parameter benchmark.

### Model 2: Autoregressive Linear Regression with L2 Regularization (Ridge)
Linear combination of secular trend, autoregressive terms, and seasonal cyclical harmonics with L2 ridge penalty ($\alpha=1.0$) to stabilize matrix inversion on short series:
$$\hat{y}_{t} = \beta_0 + \beta_1 t + \beta_2 y_{t-1} + \beta_3 y_{t-2} + \beta_4 \bar{y}_{3} + \beta_5 \sin(2\pi m/12) + \beta_6 \cos(2\pi m/12)$$

### Model 3: Random Forest Regressor (Ensemble)
Ensemble of randomized decision trees ($B=50$) with maximum tree depth constrained to $\text{depth} \le 3$ to restrict small-sample variance:
$$\hat{y}_{t} = \frac{1}{B} \sum_{b=1}^{B} T_b(x_t)$$

---

## 4. Evaluation Metrics & Selection Criterion

### 4.1. Error Metrics
1. **Mean Absolute Error (MAE):**
   $$\text{MAE} = \frac{1}{K} \sum_{i=1}^{K} |y_i - \hat{y}_i|$$
2. **Root Mean Squared Error (RMSE):**
   $$\text{RMSE} = \sqrt{\frac{1}{K} \sum_{i=1}^{K} (y_i - \hat{y}_i)^2}$$
3. **Coefficient of Determination ($R^2$):**
   $$R^2 = 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y}_{\text{test}})^2}$$

### 4.2. Mathematical Note on Negative R² in Short Time Series
In time-series literature, $R^2$ can be negative when evaluated over short test holdouts ($K \le 3$ to $6$). This occurs because the total sum of squares ($\text{TSS} = \sum (y_i - \bar{y}_{\text{test}})^2$) around the test sample mean is small. If the residual error ($\text{RSS}$) exceeds this small holdout variance, $R^2 < 0$. Predicting the holdout mean is not a permissible time-series forecasting strategy because it requires future information. Evaluating across a full 12-month annual cycle captures true seasonal variance and yields positive $R^2$.

### 4.3. Selection Criterion
The model exhibiting the **lowest RMSE** across identical chronological test folds is automatically selected as the preferred forecaster for out-of-sample forward projections.

---

## 5. Empirical Results on Building Data Genome 2 Benchmark

An empirical trial was executed using real sub-metered electricity readings from building `Bear_education_Maryjane` (Higher Education classroom & research building, 7,998.1 m², built 1964) from the Building Data Genome 2 project (Miller et al., 2020), evaluated via 12 chronological rolling folds across 2017:

- **Total Historical Observations:** 24 months (Jan 2016 to Dec 2017)
- **Initial Training Set:** 12 months (2016-01 to 2016-12)
- **Rolling Test Folds:** 12 months (2017-01 to 2017-12)
- **Total Test Variance (TSS):** Genuine seasonal variance across full operational year

### Empirical Comparative Benchmark Results:
| Candidate Model | Evaluated Features | MAE (kg CO₂e) | RMSE (kg CO₂e) | R² Score | Outcome |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Naive Baseline** | $y_{t-1}$ (persistence) | 11,601.86 | **14,057.54** | **0.4877** | Baseline Benchmark |
| **Random Forest** | Lags, Rolling Mean, Sin/Cos, Trend | 12,960.68 | 14,477.03 | 0.4567 | Evaluated |
| **Linear Regression (Ridge)** | Lags, Rolling Mean, Sin/Cos, Trend | 14,927.15 | 16,391.66 | 0.3034 | Evaluated |

### Key Experimental Insights:
1. **Persistence is a Formidable Benchmark in Energy Series:** In monthly aggregated building energy series, month-to-month persistence is extremely strong. Zero-parameter persistence models introduce zero estimation variance, making them very competitive against multi-parameter regressors on modest sample sizes.
2. **Positive R² Achieved via Annual Horizon:** Evaluating across all 12 months of the year yielded positive $R^2$ values (~0.46 to 0.49) for all models, resolving the negative $R^2$ artifact seen on tiny 3-month holdouts.
3. **Dynamic Out-of-Sample Projections:** Integrating cyclical seasonal harmonics ($\sin, \cos$) enables regularized regression models to project time-varying seasonal curves rather than repeating flatline values.

---

## 6. AI Anomaly Detection Quality Screening (Isolation Forest)

To augment data quality assurance, Carbon Ledger incorporates an unsupervised **Isolation Forest** (`services.anomaly_detector`). It screens historical records against category-relative median ratios and z-scores to flag statistical spikes or consolidation overlaps. All flagged items are classified as **"Requires Audit Investigation"** with actionable follow-up guidance, maintaining strict methodological integrity.

---

## 7. Disclaimers & Governance Notice

- Models trained on synthetic or external benchmarks demonstrate analytical pipelines; they do not substitute for on-site engineering energy audits.
- Deterministic recommendations in the platform are rule-based heuristics derived from ISO 14064 principles and are not AI-generated.
