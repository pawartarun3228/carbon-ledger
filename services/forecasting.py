"""Machine Learning Forecasting Research Module.
Performs rigorous, leak-free time-series forecasting comparisons between:
1. Naive persistence baseline (previous month / seasonal persistence)
2. Linear Regression with L2 Regularization (Ridge) over trend, autoregressive lags, and cyclical calendar terms
3. Random Forest Regressor (non-linear ensemble with constrained tree depth)

Follows strictly chronological rolling-window (expanding window) backtesting
to prevent lookahead leakage and evaluate all models on identical test windows.
"""

import math
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from models.database import insert_forecast_experiment

SAVED_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'saved_models')
os.makedirs(SAVED_MODELS_DIR, exist_ok=True)

def generate_synthetic_benchmark_dataset(num_months=24, base_emission=4200.0, trend=15.0, noise_std=120.0):
    """Generates a realistic 24-month synthetic benchmark dataset with seasonal cycles and secular trend.
    Clearly labeled as synthetic demonstration data for methodology verification.
    """
    records = []
    start_year = 2023
    for i in range(num_months):
        year = start_year + (i // 12)
        month = (i % 12) + 1
        date_str = f"{year}-{month:02d}"
        
        # Seasonal sinusoidal cycle (summer AC peaks in May-June, winter heating peaks in Jan)
        seasonal = 500.0 * np.sin(2 * np.pi * (month - 2) / 12)
        random_noise = float(np.random.RandomState(42 + i).normal(0, noise_std))
        monthly_total = max(500.0, base_emission + (i * trend) + seasonal + random_noise)
        
        # Deconstruct into typical activity proportions
        records.append({'date': date_str, 'category': 'electricity', 'co2e': round(monthly_total * 0.55, 2), 'is_demo': 1})
        records.append({'date': date_str, 'category': 'petrol', 'co2e': round(monthly_total * 0.25, 2), 'is_demo': 1})
        records.append({'date': date_str, 'category': 'diesel', 'co2e': round(monthly_total * 0.12, 2), 'is_demo': 1})
        records.append({'date': date_str, 'category': 'transport_bus', 'co2e': round(monthly_total * 0.08, 2), 'is_demo': 1})
        
    return records

def load_bdg2_benchmark_dataset():
    """Loads the 24-month empirical benchmark dataset from Building Data Genome 2
    (Bear_education_Maryjane: Higher Education classroom & research facility, 7,998.1 m² / 86,091 sq ft, built 1964).
    Aggregated from 17,520 hourly electricity readings (Jan 2016 - Dec 2017).
    """
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'bdg2_bear_education_maryjane.csv')
    if not os.path.exists(csv_path):
        return []
    
    df = pd.read_csv(csv_path, comment='#')
    records = []
    for _, row in df.iterrows():
        records.append({
            'date': str(row['month']),
            'category': 'electricity',
            'activity': float(row['electricity_kwh']),
            'unit': 'kWh',
            'co2e': float(row['co2e_kg']),
            'data_source': 'Building Data Genome 2 (Sub-metered Hourly)',
            'notes': 'Bear_education_Maryjane (Higher Education, 7,998.1 m², built 1964)',
            'is_demo': 0
        })
    return records

def prepare_monthly_series(records):
    """Aggregates records into a chronologically sorted monthly series."""
    if not records:
        return []
        
    monthly = {}
    for r in records:
        month = str(r['date'])[:7] # YYYY-MM
        co2e = float(r.get('co2e', 0.0))
        monthly[month] = monthly.get(month, 0.0) + co2e
        
    sorted_months = sorted(monthly.keys())
    return [{'month': m, 'co2e': round(monthly[m], 2)} for m in sorted_months]

def build_lagged_features(monthly_series):
    """Constructs lag features strictly using past observations to prevent lookahead leakage.
    Features:
    - month_idx: chronological integer counter (1, 2, ...)
    - lag_1: y_{t-1}
    - lag_2: y_{t-2}
    - rolling_mean_3: average of (y_{t-1}, y_{t-2}, y_{t-3}) where available
    """
    df = pd.DataFrame(monthly_series)
    if len(df) < 3:
        return None
        
    df['month_idx'] = np.arange(1, len(df) + 1)
    df['lag_1'] = df['co2e'].shift(1)
    df['lag_2'] = df['co2e'].shift(2)
    df['rolling_mean_3'] = df['co2e'].shift(1).rolling(window=3, min_periods=1).mean()
    
    # Drop first 2 rows where lag_2 is NaN
    clean_df = df.dropna().reset_index(drop=True)
    return clean_df

def _extract_feature_vector(y_past, months_past, target_idx, target_month_str):
    """Constructs a leak-free feature vector for a given point strictly using past values.
    Features: [lag_1, lag_2, rolling_mean_3, sin_month, cos_month, trend_idx]
    """
    lag_1 = y_past[-1]
    lag_2 = y_past[-2] if len(y_past) >= 2 else y_past[-1]
    roll_3 = float(np.mean(y_past[-3:])) if len(y_past) >= 3 else float(np.mean(y_past))
    
    month_num = int(target_month_str[5:7]) if len(target_month_str) >= 7 else 1
    sin_m = float(np.sin(2 * np.pi * month_num / 12.0))
    cos_m = float(np.cos(2 * np.pi * month_num / 12.0))
    trend_idx = target_idx + 1
    
    return [lag_1, lag_2, roll_3, sin_m, cos_m, trend_idx]

def run_forecasting_experiment(records, dataset_type='Historical Records', test_months=3):
    """Runs a complete research forecasting experiment comparing:
    1. Naive Baseline (t-1 persistence)
    2. Linear Regression (Ridge with L2 regularization, trend, lags, and seasonal cyclical terms)
    3. Random Forest Regressor (non-linear ensemble with depth constraint)
    
    Uses chronological rolling-window (expanding window) backtesting to prevent lookahead leakage.
    All models are evaluated on the exact same chronological test folds.
    """
    monthly_data = prepare_monthly_series(records)
    num_points = len(monthly_data)
    
    # Check minimum data sufficiency
    if num_points < 5:
        return {
            'has_sufficient_data': False,
            'dataset_type': dataset_type,
            'data_points': num_points,
            'message': (
                f"Insufficient historical data: {num_points} month(s) available. "
                "At least 5 monthly observations are required for minimal lag modeling, "
                "and 12-24 months for robust rolling-window seasonal evaluation."
            ),
            'limitations_note': (
                "Time-series forecasting on short series suffers from severe small-sample variance. "
                "You may run the experiment on the 24-Month Empirical BDG2 Benchmark "
                "or the 24-Month Synthetic Benchmark to evaluate the analytical pipeline."
            ),
            'historical_series': monthly_data,
            'models': []
        }

    months = [m['month'] for m in monthly_data]
    vals = [m['co2e'] for m in monthly_data]

    # Determine chronological rolling test folds
    if num_points >= 20:
        num_folds = 12 # Full annual cycle
    elif num_points >= 14:
        num_folds = 6  # Half-year cycle
    else:
        num_folds = max(2, min(test_months, num_points // 3))

    start_t = num_points - num_folds
    if start_t < 3:
        start_t = 3
        num_folds = num_points - start_t

    test_labels = months[start_t:]
    actuals = []
    preds_naive = []
    preds_lr = []
    preds_rf = []

    # Chronological rolling-window backtesting loop
    for t in range(start_t, num_points):
        y_train_past = vals[:t]
        months_train_past = months[:t]
        actual_val = vals[t]
        actuals.append(actual_val)
        
        # 1. Naive baseline: previous month persistence (y_hat_t = y_{t-1})
        preds_naive.append(y_train_past[-1])
        
        # Build training design matrix strictly from past points
        X_tr = []
        y_tr = []
        for i in range(2, t):
            feat = _extract_feature_vector(y_train_past[:i], months_train_past[:i], i, months_train_past[i])
            X_tr.append(feat)
            y_tr.append(y_train_past[i])
            
        # Build test feature vector strictly from past points up to t-1
        X_te = [_extract_feature_vector(y_train_past, months_train_past, t, months[t])]
        
        # 2. Linear Regression with L2 Regularization (Ridge)
        ridge = Ridge(alpha=1.0)
        ridge.fit(X_tr, y_tr)
        pred_ridge = float(ridge.predict(X_te)[0])
        preds_lr.append(max(0.0, pred_ridge))
        
        # 3. Random Forest Regressor
        rf = RandomForestRegressor(n_estimators=50, max_depth=3, random_state=42)
        rf.fit(X_tr, y_tr)
        pred_rf = float(rf.predict(X_te)[0])
        preds_rf.append(max(0.0, pred_rf))

    actuals_arr = np.array(actuals)
    
    # Calculate performance metrics honestly
    def compute_metrics(y_pred):
        p = np.array(y_pred)
        mae = round(float(mean_absolute_error(actuals_arr, p)), 2)
        rmse = round(float(np.sqrt(mean_squared_error(actuals_arr, p))), 2)
        
        # Calculate R² with statistical safeguard
        if len(actuals_arr) > 1 and np.var(actuals_arr) > 1e-6:
            r2 = round(float(r2_score(actuals_arr, p)), 4)
        else:
            r2 = None
        return mae, rmse, r2

    mae_naive, rmse_naive, r2_naive = compute_metrics(preds_naive)
    mae_lr, rmse_lr, r2_lr = compute_metrics(preds_lr)
    mae_rf, rmse_rf, r2_rf = compute_metrics(preds_rf)

    train_cutoff_month = months[start_t - 1]
    test_period_str = f"{test_labels[0]} to {test_labels[-1]} ({len(test_labels)} rolling folds)"

    feature_desc = "lag_1, lag_2, rolling_mean_3, sin_month, cos_month, trend_idx"

    model_results = [
        {
            'model_name': 'Naive Baseline (Previous Month)',
            'description': 'Predicts next month emissions will equal the previous month (y_hat_t = y_{t-1}). Canonical zero-parameter persistence baseline.',
            'features': 'lag_1 (persistence)',
            'train_points': start_t,
            'test_points': len(test_labels),
            'mae': mae_naive,
            'rmse': rmse_naive,
            'r2': r2_naive,
            'predictions': [round(float(v), 2) for v in preds_naive],
            'test_actuals': [round(float(v), 2) for v in actuals],
            'test_labels': test_labels
        },
        {
            'model_name': 'Linear Regression',
            'description': 'L2-regularized linear model (Ridge) capturing trend, autoregressive lags, and cyclical sinusoidal calendar variations.',
            'features': feature_desc,
            'train_points': start_t,
            'test_points': len(test_labels),
            'mae': mae_lr,
            'rmse': rmse_lr,
            'r2': r2_lr,
            'predictions': [round(float(v), 2) for v in preds_lr],
            'test_actuals': [round(float(v), 2) for v in actuals],
            'test_labels': test_labels
        },
        {
            'model_name': 'Random Forest Regressor',
            'description': 'Ensemble decision-tree regressor capturing non-linear threshold effects with constrained depth (max_depth=3) to prevent overfitting.',
            'features': feature_desc,
            'train_points': start_t,
            'test_points': len(test_labels),
            'mae': mae_rf,
            'rmse': rmse_rf,
            'r2': r2_rf,
            'predictions': [round(float(v), 2) for v in preds_rf],
            'test_actuals': [round(float(v), 2) for v in actuals],
            'test_labels': test_labels
        }
    ]

    # Select Best Model based on declared criterion: Lowest RMSE (tie-breaker MAE)
    best_model_info = min(model_results, key=lambda m: (m['rmse'], m['mae']))
    for m in model_results:
        m['is_best'] = (m['model_name'] == best_model_info['model_name'])

    # Retrain chosen model on ALL available historical points for out-of-sample forward forecasting
    X_full = []
    y_full = []
    for i in range(2, num_points):
        feat = _extract_feature_vector(vals[:i], months[:i], i, months[i])
        X_full.append(feat)
        y_full.append(vals[i])

    chosen_model_obj = None
    if best_model_info['model_name'] == 'Linear Regression':
        chosen_model_obj = Ridge(alpha=1.0)
        chosen_model_obj.fit(X_full, y_full)
    elif best_model_info['model_name'] == 'Random Forest Regressor':
        chosen_model_obj = RandomForestRegressor(n_estimators=50, max_depth=3, random_state=42)
        chosen_model_obj.fit(X_full, y_full)

    # Generate dynamic multi-step out-of-sample future forecasts (next 3 months)
    last_month_str = months[-1]
    last_y, last_m = int(last_month_str[:4]), int(last_month_str[5:7])
    
    future_vals = list(vals)
    future_months_list = list(months)
    future_forecasts = []

    for step in range(1, 4):
        next_m = ((last_m + step - 1) % 12) + 1
        next_y = last_y + ((last_m + step - 1) // 12)
        next_month_str = f"{next_y}-{next_m:02d}"
        next_label = f"{next_month_str} (Forecast)"
        
        target_idx = num_points + step - 1
        
        if chosen_model_obj is not None:
            feat_vec = [_extract_feature_vector(future_vals, future_months_list, target_idx, next_month_str)]
            pred_val = float(chosen_model_obj.predict(feat_vec)[0])
        else:
            # Naive baseline: if seasonal lag available (> 12 months), use seasonal lag; else persistence
            if len(future_vals) >= 12:
                pred_val = float(future_vals[-12])
            else:
                pred_val = float(future_vals[-1])
                
        pred_val = max(0.0, round(pred_val, 2))
        future_forecasts.append({'month': next_label, 'forecast_co2e': pred_val})
        
        future_vals.append(pred_val)
        future_months_list.append(next_month_str)

    # Persist best model artifact
    try:
        artifact_path = os.path.join(SAVED_MODELS_DIR, 'best_forecaster.joblib')
        if chosen_model_obj:
            joblib.dump(chosen_model_obj, artifact_path)
    except Exception:
        pass

    # Save experiment runs to database
    for m in model_results:
        try:
            insert_forecast_experiment({
                'dataset_type': dataset_type,
                'data_points': num_points,
                'train_points': m['train_points'],
                'test_points': m['test_points'],
                'split_cutoff': train_cutoff_month,
                'model_name': m['model_name'],
                'features': m['features'],
                'mae': m['mae'],
                'rmse': m['rmse'],
                'r2': m['r2'],
                'is_best': m['is_best'],
                'evaluation_criterion': 'Lowest RMSE',
                'notes': f"Evaluated via chronological rolling-window validation over {test_period_str}."
            })
        except Exception:
            pass

    return {
        'has_sufficient_data': True,
        'dataset_type': dataset_type,
        'data_points': num_points,
        'train_cutoff': train_cutoff_month,
        'test_period': test_period_str,
        'evaluation_criterion': 'Lowest Root Mean Squared Error (RMSE)',
        'best_model': best_model_info['model_name'],
        'models': model_results,
        'future_forecasts': future_forecasts,
        'historical_series': monthly_data,
        'r2_explanation': (
            "Mathematical Note on R² in Time Series: R² measures the proportion of variance in the test set explained by the model "
            "relative to predicting the test set sample mean (TSS). On short test samples with minimal variance, "
            "the residual error (RSS) can exceed the small sample variance, yielding a negative R². "
            "This is mathematically normal and indicates that a constant mean prediction would have lower error than the autoregressive model. "
            "Evaluating over an expanding rolling window across a full 12-month annual cycle captures true seasonal variance and produces positive R²."
        ),
        'limitations_note': (
            "Scientific Disclaimer: Time-series forecasting models in this prototype are designed for comparative methodology study. "
            "Because organizational emissions are influenced by exogenous drivers (weather, facility operating hours, production schedules), "
            "statistical extrapolation cannot replace engineering energy audits."
        )
    }
