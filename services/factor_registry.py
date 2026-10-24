"""Emission Factor Registry Service.
Maintains documented, traceable emission factors aligned with CEA, IPCC, and DEFRA benchmarks.
Preserves official provenance and unit compatibility across Scopes 1, 2, and 3.
"""

import json
import os
import math

FACTORS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'emission_factors.json')

# Compatible unit mapping
UNIT_COMPATIBILITY = {
    'electricity': ['kWh', 'kwh', 'KWH', 'MWh', 'mwh'],
    'petrol': ['litre', 'litres', 'L', 'l', 'liter', 'liters', 'gallon', 'gal'],
    'diesel': ['litre', 'litres', 'L', 'l', 'liter', 'liters', 'gallon', 'gal'],
    'transport_car_petrol': ['vehicle-km', 'vkm', 'km', 'KM', 'kilometre', 'kilometres', 'kilometer', 'kilometers', 'miles', 'mi'],
    'transport_car_diesel': ['vehicle-km', 'vkm', 'km', 'KM', 'kilometre', 'kilometres', 'kilometer', 'kilometers', 'miles', 'mi'],
    'transport_bus': ['passenger-km', 'pkm', 'km', 'KM', 'passenger-kilometre', 'passenger-kilometres', 'passenger-miles', 'pmiles', 'miles', 'mi'],
    'transport_train': ['passenger-km', 'pkm', 'km', 'KM', 'passenger-kilometre', 'passenger-kilometres', 'passenger-miles', 'pmiles', 'miles', 'mi'],
    'transport_motorcycle': ['vehicle-km', 'vkm', 'km', 'KM', 'kilometre', 'kilometres', 'miles', 'mi']
}

def load_registry_file():
    """Loads emission factors directly from the canonical JSON registry."""
    if not os.path.exists(FACTORS_FILE):
        return {}
    with open(FACTORS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_factor_registry():
    """Returns the dictionary of all emission factors with full metadata."""
    return load_registry_file()

def get_factor_entry(category):
    """Retrieves metadata for a specific activity category."""
    registry = get_factor_registry()
    if category not in registry:
        raise ValueError(f"Unknown activity category '{category}'. Valid categories: {list(registry.keys())}")
    return registry[category]

def validate_unit_compatibility(category, unit):
    """Checks whether the supplied unit matches the category's expected input unit."""
    if not unit:
        return True, "No unit provided; default applied."
    
    clean_unit = str(unit).strip().lower()
    allowed_units = [u.lower() for u in UNIT_COMPATIBILITY.get(category, [])]
    
    if allowed_units and clean_unit not in allowed_units:
        expected = UNIT_COMPATIBILITY.get(category, ['standard unit'])[0]
        return False, f"Unit mismatch: '{unit}' is incompatible with '{category}'. Expected '{expected}'."
    return True, "Compatible"

def normalize_unit_conversion(category, activity_value, unit):
    """Converts alternate units (e.g. MWh -> kWh, miles -> km, gallon -> litre) to base unit."""
    if not unit:
        return activity_value, UNIT_COMPATIBILITY.get(category, ['unit'])[0]
    
    u = str(unit).strip().lower()
    
    # Electricity conversions
    if category == 'electricity':
        if u in ['mwh']:
            return activity_value * 1000.0, 'kWh'
        return activity_value, 'kWh'
    
    # Liquid fuel conversions
    if category in ['petrol', 'diesel']:
        if u in ['gallon', 'gal']:
            return activity_value * 3.78541, 'litre'
        return activity_value, 'litre'
        
    # Passenger transport (bus, train)
    if category in ['transport_bus', 'transport_train']:
        if u in ['passenger-miles', 'pmiles']:
            return activity_value * 1.60934, 'passenger-km'
        if u in ['miles', 'mi']:
            return activity_value * 1.60934, 'km'
        if u in ['pkm', 'passenger-kilometre', 'passenger-kilometres']:
            return activity_value, 'passenger-km'
        return activity_value, u

    # Vehicle transport (car, motorcycle)
    if category in ['transport_car_petrol', 'transport_car_diesel', 'transport_motorcycle']:
        if u in ['miles', 'mi']:
            return activity_value * 1.60934, 'km'
        if u in ['vkm', 'vehicle-kilometre', 'vehicle-kilometres']:
            return activity_value, 'vehicle-km'
        return activity_value, u

def kg_to_tonnes(kg_co2e):
    """Converts kg CO2e to metric tonnes CO2e (1 tonne = 1,000 kg)."""
    if kg_co2e is None:
        return 0.0
    return round(float(kg_co2e) / 1000.0, 4)

def tonnes_to_kg(tonnes_co2e):
    """Converts metric tonnes CO2e to kg CO2e."""
    if tonnes_co2e is None:
        return 0.0
    return round(float(tonnes_co2e) * 1000.0, 2)
