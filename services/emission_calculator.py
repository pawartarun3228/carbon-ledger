"""Emission Calculation Engine.
Calculates greenhouse gas emissions based on activity data and compatible emission factors.
Formula: Emissions (kg CO2e) = Activity Quantity × Compatible Emission Factor
Preserves source provenance, versions, and boundaries.
"""

import math
import os
import json
from services.factor_registry import (
    get_factor_registry, 
    get_factor_entry, 
    validate_unit_compatibility, 
    normalize_unit_conversion,
    kg_to_tonnes
)

def load_emission_factors():
    """Returns all emission factors from the registry file."""
    return get_factor_registry()

def calculate_emission(category, activity_value, unit=None):
    """Calculates CO2e for a given activity and category.
    
    Args:
        category (str): Category key (e.g. 'electricity', 'petrol', 'diesel')
        activity_value (float/int): Quantity of activity
        unit (str, optional): Unit of activity. If provided, unit compatibility is verified.
        
    Returns:
        dict: Calculation results including kg CO2e, tonnes CO2e, factor, and provenance.
        
    Raises:
        ValueError: If input is invalid, non-finite, non-positive, or category is unknown.
    """
    if category is None:
        raise ValueError("Category cannot be None.")
        
    # Check numeric validity
    try:
        activity_float = float(activity_value)
    except (TypeError, ValueError):
        raise ValueError(f"Activity value must be a valid number, got '{activity_value}'.")
        
    if math.isnan(activity_float) or math.isinf(activity_float):
        raise ValueError(f"Activity value must be finite, got '{activity_value}'.")
        
    if activity_float <= 0:
        raise ValueError("Activity value must be a positive number")
        
    factors = load_emission_factors()
    if category not in factors:
        raise ValueError(f"Invalid category: {category}")
        
    factor_data = factors[category]
    factor_value = factor_data['factor']
    expected_unit = factor_data.get('unit', '')
    
    # Unit compatibility check
    if unit:
        is_compat, msg = validate_unit_compatibility(category, unit)
        if not is_compat:
            raise ValueError(msg)
        norm_activity, calc_unit = normalize_unit_conversion(category, activity_float, unit)
    else:
        norm_activity = activity_float
        calc_unit = expected_unit
        
    co2e_kg = round(norm_activity * factor_value, 4)
    co2e_t = kg_to_tonnes(co2e_kg)
    
    return {
        'category': category,
        'category_name': factor_data.get('name', category),
        'activity': activity_float,
        'unit': unit if unit else expected_unit,
        'normalized_activity': round(norm_activity, 4),
        'calc_unit': calc_unit,
        'emission_factor': factor_value,
        'factor_unit': factor_data.get('factor_unit', 'kg CO2e/unit'),
        'co2e': co2e_kg,
        'co2e_tonnes': co2e_t,
        'scope': factor_data.get('scope', 'Scope 1'),
        'source': factor_data.get('source', 'Unknown Source'),
        'source_url': factor_data.get('source_url', ''),
        'version': factor_data.get('version', 'v1.0'),
        'region': factor_data.get('region', 'Global'),
        'notes': factor_data.get('notes', '')
    }

def get_available_categories():
    """Returns list of categories formatted for forms and dropdowns."""
    factors = load_emission_factors()
    return [{'key': k, 'name': v['name'], 'unit': v['unit'], 'scope': v.get('scope', 'Scope 1')} 
            for k, v in factors.items()]

def get_category_display_group(category):
    """Categorizes activities into high-level groups for reporting."""
    if not category:
        return 'other'
    if category == 'electricity':
        return 'electricity'
    elif category in ('petrol', 'diesel'):
        return 'fuel'
    elif category.startswith('transport_'):
        return 'transportation'
    return 'other'
