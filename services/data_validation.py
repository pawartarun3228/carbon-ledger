"""Data Validation Service.
Provides robust schema, type, range, unit compatibility, and duplicate checking for manual and CSV entries.
Never silently converts missing or invalid values to zero.
"""

import re
import csv
import io
import math
from services.factor_registry import get_factor_registry, validate_unit_compatibility
from models.database import check_duplicate_record

DATE_PATTERN = re.compile(r'^\d{4}-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?$')

ALLOWED_DATA_SOURCES = [
    'Utility Bill',
    'Fuel Receipt',
    'Travel Log',
    'Commute Survey',
    'Direct Metering',
    'Estimated',
    'Synthetic Demo',
    'Manual Entry'
]

def validate_date_format(date_str):
    """Validates date format as YYYY-MM or YYYY-MM-DD."""
    if not date_str or not isinstance(date_str, str):
        return False, "Date cannot be empty."
    clean_date = date_str.strip()
    if not DATE_PATTERN.match(clean_date):
        return False, f"Invalid date format '{date_str}'. Expected YYYY-MM or YYYY-MM-DD."
    return True, clean_date

def validate_activity_quantity(value_str):
    """Validates activity value is a positive, finite number."""
    if value_str is None or str(value_str).strip() == '':
        return False, "Activity quantity is missing."
    try:
        val = float(value_str)
    except (ValueError, TypeError):
        return False, f"Activity quantity '{value_str}' is not a valid number."
        
    if math.isnan(val) or math.isinf(val):
        return False, "Activity quantity must be a finite number."
        
    if val <= 0:
        return False, f"Activity quantity must be strictly greater than zero (got {val})."
        
    return True, val

def validate_activity_entry(date_str, category, activity_str, unit=None, data_source='Manual Entry', notes=''):
    """Validates a single activity entry completely.
    Returns (is_valid, result_dict, error_message).
    """
    # 1. Date
    ok, date_res = validate_date_format(date_str)
    if not ok:
        return False, None, date_res
    date_val = date_res

    # 2. Category
    registry = get_factor_registry()
    if not category or category not in registry:
        return False, None, f"Invalid or missing activity category: '{category}'."

    # 3. Activity
    ok, act_res = validate_activity_quantity(activity_str)
    if not ok:
        return False, None, act_res
    activity_val = act_res

    # 4. Unit
    expected_unit = registry[category].get('unit', '')
    resolved_unit = unit if unit and str(unit).strip() else expected_unit
    is_compat, unit_msg = validate_unit_compatibility(category, resolved_unit)
    if not is_compat:
        return False, None, unit_msg

    # 5. Data Source
    source_val = data_source if data_source in ALLOWED_DATA_SOURCES else 'Manual Entry'

    # 6. Check duplicate in database
    duplicates = check_duplicate_record(date_val, category, activity_val)
    duplicate_warning = None
    if duplicates:
        duplicate_warning = f"Notice: Potential duplicate record found (ID #{duplicates[0]['id']} with same date, category, and quantity)."

    return True, {
        'date': date_val,
        'category': category,
        'activity': activity_val,
        'unit': resolved_unit,
        'data_source': source_val,
        'notes': str(notes).strip() if notes else '',
        'duplicate_warning': duplicate_warning
    }, None

def validate_csv_content(csv_text_or_stream):
    """Parses and validates a CSV input file with helpful row-specific diagnostics.
    Returns:
        valid_rows: list of validated dictionaries ready for insertion
        errors: list of error strings with row numbers
        warnings: list of warning strings with row numbers
    """
    valid_rows = []
    errors = []
    warnings = []

    if isinstance(csv_text_or_stream, str):
        f = io.StringIO(csv_text_or_stream)
    else:
        # File-like stream
        f = io.TextIOWrapper(csv_text_or_stream, encoding='utf-8-sig', errors='replace')

    reader = csv.DictReader(f)
    if not reader.fieldnames:
        return [], ["CSV file is empty or cannot be parsed."], []

    # Clean header names (strip BOM, whitespace, lowercase)
    field_map = {col.strip().lower().replace(' ', '_'): col for col in reader.fieldnames if col}
    
    required_cols = ['date', 'category', 'activity']
    missing_cols = [c for c in required_cols if c not in field_map]
    if missing_cols:
        return [], [f"CSV missing mandatory column(s): {', '.join(missing_cols)}. Required columns are 'date', 'category', 'activity'."], []

    seen_in_batch = set()

    for row_idx, row in enumerate(reader, start=2): # Line 2 is first data row
        date_raw = row.get(field_map['date'])
        cat_raw = row.get(field_map['category'])
        act_raw = row.get(field_map['activity'])
        
        unit_raw = row.get(field_map.get('unit', ''))
        source_raw = row.get(field_map.get('data_source', ''))
        notes_raw = row.get(field_map.get('notes', ''))

        # Check empty row
        if not any([date_raw, cat_raw, act_raw]):
            continue

        ok, result, err = validate_activity_entry(
            date_raw, 
            cat_raw.strip().lower() if cat_raw else '', 
            act_raw, 
            unit_raw, 
            source_raw.strip() if source_raw else 'Manual Entry', 
            notes_raw
        )

        if not ok:
            errors.append(f"Row {row_idx}: {err}")
            continue

        # In-batch duplicate check
        batch_key = (result['date'], result['category'], round(result['activity'], 4))
        if batch_key in seen_in_batch:
            warnings.append(f"Row {row_idx}: Warning - Duplicate entry in this CSV batch for {result['category']} on {result['date']}.")
        else:
            seen_in_batch.add(batch_key)

        if result.get('duplicate_warning'):
            warnings.append(f"Row {row_idx}: {result['duplicate_warning']}")

        valid_rows.append(result)

    return valid_rows, errors, warnings
