"""Emission Data Aggregation and Analytics Service.
Provides multi-dimensional summaries (by category, scope, reporting month),
data-quality checks, and unit conversion between kg CO2e and metric tonnes CO2e.
"""

from collections import defaultdict
from services.factor_registry import kg_to_tonnes
from services.emission_calculator import get_category_display_group, load_emission_factors

def aggregate_emissions(records, date_from=None, date_to=None):
    """Performs multi-dimensional aggregation across a set of emission records.
    
    Args:
        records (list): List of emission record dicts.
        date_from (str, optional): Filter from date (inclusive).
        date_to (str, optional): Filter to date (inclusive).
        
    Returns:
        dict: Summary statistics, breakdown by category and scope, monthly series, and data quality warnings.
    """
    if not records:
        return {
            'total_kg': 0.0,
            'total_tonnes': 0.0,
            'record_count': 0,
            'date_range': {'start': None, 'end': None},
            'categories': {},
            'scopes': {'Scope 1': 0.0, 'Scope 2': 0.0, 'Scope 3': 0.0},
            'groups': {'electricity': 0.0, 'fuel': 0.0, 'transportation': 0.0, 'other': 0.0},
            'monthly_totals': {},
            'monthly_series': [],
            'highest_category': None,
            'highest_category_pct': 0.0,
            'highest_group': None,
            'highest_group_pct': 0.0,
            'data_quality_warnings': ["No activity records found in the database. Add activities or load demonstration data to begin."]
        }

    # Apply date filters if specified
    filtered = []
    for r in records:
        d = r['date']
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        filtered.append(r)

    if not filtered:
        return {
            'total_kg': 0.0,
            'total_tonnes': 0.0,
            'record_count': 0,
            'date_range': {'start': date_from, 'end': date_to},
            'categories': {},
            'scopes': {'Scope 1': 0.0, 'Scope 2': 0.0, 'Scope 3': 0.0},
            'groups': {'electricity': 0.0, 'fuel': 0.0, 'transportation': 0.0, 'other': 0.0},
            'monthly_totals': {},
            'monthly_series': [],
            'highest_category': None,
            'highest_category_pct': 0.0,
            'highest_group': None,
            'highest_group_pct': 0.0,
            'data_quality_warnings': ["No records match the selected reporting period filter."]
        }

    factors = load_emission_factors()
    
    total_kg = 0.0
    cat_totals = defaultdict(float)
    cat_counts = defaultdict(int)
    scope_totals = defaultdict(float)
    group_totals = defaultdict(float)
    monthly_data = defaultdict(lambda: {'total': 0.0, 'electricity': 0.0, 'fuel': 0.0, 'transportation': 0.0, 'other': 0.0})
    demo_count = 0
    all_dates = set()

    for r in filtered:
        co2e = float(r.get('co2e', 0.0))
        cat = r.get('category', 'unknown')
        date = r.get('date', 'unknown')
        month_key = date[:7] # Normalize to YYYY-MM
        all_dates.add(month_key)
        
        if r.get('is_demo'):
            demo_count += 1
            
        total_kg += co2e
        cat_totals[cat] += co2e
        cat_counts[cat] += 1
        
        # Scope classification
        scope = factors.get(cat, {}).get('scope', 'Scope 1')
        scope_totals[scope] += co2e
        
        # Group classification
        grp = get_category_display_group(cat)
        group_totals[grp] += co2e
        
        # Monthly accumulation
        monthly_data[month_key]['total'] += co2e
        monthly_data[month_key][grp] += co2e

    total_kg = round(total_kg, 4)
    total_tonnes = kg_to_tonnes(total_kg)

    # Categories formatted
    cat_breakdown = {}
    for cat, val in cat_totals.items():
        factor_info = factors.get(cat, {})
        pct = (val / total_kg * 100.0) if total_kg > 0 else 0.0
        cat_breakdown[cat] = {
            'name': factor_info.get('name', cat.title()),
            'category': cat,
            'kg_co2e': round(val, 2),
            'tonnes_co2e': kg_to_tonnes(val),
            'percentage': round(pct, 1),
            'count': cat_counts[cat],
            'scope': factor_info.get('scope', 'Scope 1'),
            'unit': factor_info.get('unit', '')
        }

    # Find highest category
    highest_cat = None
    highest_cat_pct = 0.0
    if cat_breakdown:
        highest_cat_key = max(cat_totals, key=cat_totals.get)
        highest_cat = cat_breakdown[highest_cat_key]['name']
        highest_cat_pct = cat_breakdown[highest_cat_key]['percentage']

    # Find highest group
    highest_grp = None
    highest_grp_pct = 0.0
    if group_totals and total_kg > 0:
        highest_grp_key = max(group_totals, key=group_totals.get)
        highest_grp = highest_grp_key.title()
        highest_grp_pct = round((group_totals[highest_grp_key] / total_kg) * 100.0, 1)

    # Chronologically sorted monthly series
    sorted_months = sorted(monthly_data.keys())
    monthly_series = []
    for m in sorted_months:
        d = monthly_data[m]
        monthly_series.append({
            'month': m,
            'total_kg': round(d['total'], 2),
            'total_tonnes': kg_to_tonnes(d['total']),
            'electricity_kg': round(d['electricity'], 2),
            'fuel_kg': round(d['fuel'], 2),
            'transportation_kg': round(d['transportation'], 2),
            'other_kg': round(d['other'], 2)
        })

    # Data Quality Auditing
    warnings = []
    if demo_count > 0:
        warnings.append(f"Demonstration data is currently loaded ({demo_count} synthetic records). Use 'Clear Demo Data' before official reporting.")
    
    if len(sorted_months) < 6:
        warnings.append(f"Data spans only {len(sorted_months)} monthly period(s). Machine learning forecasts require at least 6 consecutive months for reasonable statistical stability.")

    # Check for missing months in between min and max date
    if len(sorted_months) >= 2:
        start_year, start_m = int(sorted_months[0][:4]), int(sorted_months[0][5:7])
        end_year, end_m = int(sorted_months[-1][:4]), int(sorted_months[-1][5:7])
        expected_months = (end_year - start_year) * 12 + (end_m - start_m) + 1
        missing_count = expected_months - len(sorted_months)
        if missing_count > 0:
            warnings.append(f"Potential reporting gap detected: {missing_count} month(s) between {sorted_months[0]} and {sorted_months[-1]} have no recorded activities.")

    if scope_totals['Scope 2'] == 0:
        warnings.append("Scope 2 electricity records are currently missing from the inventory.")

    return {
        'total_kg': total_kg,
        'total_tonnes': total_tonnes,
        'record_count': len(filtered),
        'date_range': {'start': sorted_months[0] if sorted_months else None, 'end': sorted_months[-1] if sorted_months else None},
        'categories': cat_breakdown,
        'scopes': {k: round(v, 2) for k, v in scope_totals.items()},
        'groups': {k: round(v, 2) for k, v in group_totals.items()},
        'monthly_totals': {m: round(monthly_data[m]['total'], 2) for m in sorted_months},
        'monthly_series': monthly_series,
        'highest_category': highest_cat,
        'highest_category_pct': highest_cat_pct,
        'highest_group': highest_grp,
        'highest_group_pct': highest_grp_pct,
        'data_quality_warnings': warnings
    }
