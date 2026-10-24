"""Prediction service maintaining backward compatibility for legacy tests and quick single-step projections.
For multi-model chronological experimentation, see services.forecasting.
"""

import numpy as np
from sklearn.linear_model import LinearRegression

def predict_next_month(emission_records):
    """Generates a simple trend prediction for the next month based on monthly totals."""
    # Aggregate by month
    monthly_totals = {}
    for r in emission_records:
        month = str(r['date'])[:7]
        monthly_totals[month] = monthly_totals.get(month, 0) + float(r.get('co2e', 0.0))
        
    sorted_months = sorted(monthly_totals.keys())
    values = [monthly_totals[m] for m in sorted_months]
    
    if len(values) < 4:
        return {
            'has_sufficient_data': False,
            'message': 'Need at least 4 months of data to generate a prediction.',
            'predicted_value': None,
            'model_type': 'Linear Regression',
            'data_points': len(values),
            'historical': {'labels': sorted_months, 'values': values},
            'predicted': None,
            'r_squared': None
        }
        
    X = np.array(range(1, len(values) + 1)).reshape(-1, 1)
    y = np.array(values)
    
    try:
        model = LinearRegression()
        model.fit(X, y)
        
        r_squared = model.score(X, y)
        next_x = np.array([[len(values) + 1]])
        predicted_val = model.predict(next_x)[0]
        
        return {
            'has_sufficient_data': True,
            'message': 'Prediction generated successfully.',
            'predicted_value': round(float(predicted_val), 2),
            'model_type': 'Linear Regression',
            'data_points': len(values),
            'historical': {'labels': sorted_months, 'values': [round(v, 2) for v in values]},
            'predicted': {'label': 'Next Month', 'value': round(float(predicted_val), 2)},
            'r_squared': round(float(r_squared), 4)
        }
    except Exception as e:
        return {
            'has_sufficient_data': False,
            'message': f'Error generating prediction: {str(e)}',
            'predicted_value': None,
            'model_type': 'Linear Regression',
            'data_points': len(values),
            'historical': {'labels': sorted_months, 'values': values},
            'predicted': None,
            'r_squared': None
        }
