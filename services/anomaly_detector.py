"""Machine Learning Anomaly Detection Service for Activity Data Quality.
Uses Scikit-learn's Isolation Forest to identify statistically uncharacteristic 
activity records (consumption spikes, unexpected dips, or potential multi-month overlaps).

Methodological Integrity:
- Flagged entries are strictly classified as "Requires Audit Investigation", 
  never as confirmed errors or invalid data.
- Handles heterogeneous categories by standardizing features against category medians.
- Provides human-interpretable explanations and recommended verification steps.
"""

import math
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

def detect_activity_anomalies(records, contamination=0.08):
    """Screens activity records for statistical anomalies using an Isolation Forest.
    
    Args:
        records (list of dict): List of activity/emission records from the database.
        contamination (float): Expected proportion of outliers (default 8%).
        
    Returns:
        dict: Inspection summary, flagged records count, and detailed audit items.
    """
    if not records or len(records) < 8:
        return {
            'has_sufficient_data': False,
            'message': f"Insufficient records for statistical anomaly modeling ({len(records) if records else 0} records available; at least 8 required across categories).",
            'total_inspected': len(records) if records else 0,
            'anomalies_flagged': 0,
            'flagged_records': [],
            'methodology_note': (
                "Audit Flag Disclaimer: Anomaly detection flags statistical deviations based on Isolation Forest density scoring. "
                "Flagged records are NOT confirmed errors; they indicate entries that warrant human auditor verification "
                "(e.g., seasonal peak loads, multi-month consolidated bills, or meter multiplier checks)."
            )
        }

    # Convert to DataFrame
    df = pd.DataFrame(records).copy()
    df['activity'] = pd.to_numeric(df.get('activity', 0.0), errors='coerce').fillna(0.0)
    df['co2e'] = pd.to_numeric(df.get('co2e', 0.0), errors='coerce').fillna(0.0)
    
    # Calculate category baselines (median and interquartile range for robust scaling)
    cat_medians = df.groupby('category')['activity'].transform('median').replace(0.0, 1.0)
    cat_stds = df.groupby('category')['activity'].transform('std').fillna(1.0).replace(0.0, 1.0)
    
    # Feature 1: Ratio of activity to category median
    df['ratio_to_median'] = df['activity'] / cat_medians
    
    # Feature 2: Category z-score
    df['z_score'] = (df['activity'] - cat_medians) / cat_stds
    
    # Feature 3: Log-transformed activity
    df['log_activity'] = np.log1p(np.maximum(0.0, df['activity'].values))
    
    # Feature 4: Raw CO2e
    df['co2e_feature'] = df['co2e']

    # Design matrix for Isolation Forest
    feature_cols = ['ratio_to_median', 'z_score', 'log_activity', 'co2e_feature']
    X = df[feature_cols].values
    
    # Fit Isolation Forest
    # Using fixed random_state for reproducible audit trails
    iso = IsolationForest(
        n_estimators=100,
        contamination=min(contamination, 0.15),
        random_state=42
    )
    preds = iso.fit_predict(X)
    scores = iso.decision_function(X) # lower score = more abnormal
    
    df['is_anomaly'] = (preds == -1)
    df['anomaly_score'] = np.round(scores, 4)

    flagged_records = []
    
    for idx, row in df.iterrows():
        # Only treat as genuine audit flag if Isolation Forest flagged it AND ratio or z-score shows tangible deviation
        ratio = float(row['ratio_to_median'])
        z = float(row['z_score'])
        
        if row['is_anomaly'] and (ratio >= 2.0 or ratio <= 0.35 or abs(z) >= 1.9):
            rec_id = row.get('id', idx)
            cat = str(row.get('category', 'unknown'))
            act_val = float(row.get('activity', 0.0))
            unit = str(row.get('unit', ''))
            date_val = str(row.get('date', ''))
            notes = str(row.get('notes', ''))
            
            med_val = float(cat_medians.iloc[idx])
            
            # Formulate clear, human-understandable audit explanation
            if ratio >= 2.0 or z >= 1.9:
                flag_type = "Uncharacteristic High Spike"
                explanation = (
                    f"Reported {act_val:,.1f} {unit} is {ratio:.1f}× the historical category median "
                    f"({med_val:,.1f} {unit})."
                )
                action = (
                    "Verify utility bill for potential multi-month billing consolidation, "
                    "extreme seasonal heating/cooling peak, or meter multiplier discrepancies."
                )
            else:
                flag_type = "Uncharacteristic Low Dip"
                explanation = (
                    f"Reported {act_val:,.1f} {unit} is significantly below expected operating volume "
                    f"({ratio*100:.0f}% of category median {med_val:,.1f} {unit})."
                )
                action = (
                    "Confirm whether facility was partially offline (e.g. academic recess, remote working) "
                    "or if supplementary receipts for this period are pending."
                )
                
            flagged_records.append({
                'record_id': rec_id,
                'date': date_val,
                'category': cat,
                'activity': act_val,
                'unit': unit,
                'co2e': round(float(row.get('co2e', 0.0)), 2),
                'flag_type': flag_type,
                'explanation': explanation,
                'recommended_action': action,
                'audit_status': 'Requires Audit Investigation',
                'notes': notes,
                'relative_ratio': round(ratio, 2)
            })

    # Sort flagged records by date descending
    flagged_records.sort(key=lambda r: str(r['date']), reverse=True)

    return {
        'has_sufficient_data': True,
        'total_inspected': len(records),
        'anomalies_flagged': len(flagged_records),
        'flagged_records': flagged_records,
        'algorithm': 'Isolation Forest (Scikit-Learn Ensemble)',
        'features_used': 'Category relative ratio, category z-score, log volume, total CO2e',
        'methodology_note': (
            "Audit Flag Disclaimer: Anomaly detection flags statistical deviations based on Isolation Forest density scoring. "
            "Flagged records are NOT confirmed errors; they indicate entries that warrant human auditor verification "
            "(e.g., seasonal peak loads, multi-month consolidated bills, or meter multiplier checks)."
        )
    }
