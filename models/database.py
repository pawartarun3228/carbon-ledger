import sqlite3
import os
import json

def get_db_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emission_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        activity REAL NOT NULL,
        unit TEXT NOT NULL,
        emission_factor REAL NOT NULL,
        co2e REAL NOT NULL,
        data_source TEXT DEFAULT 'Manual Entry',
        notes TEXT DEFAULT '',
        factor_source TEXT DEFAULT '',
        factor_version TEXT DEFAULT '',
        is_demo INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    ''')

    # Safely migrate existing databases if new columns are missing
    cursor.execute("PRAGMA table_info(emission_records)")
    columns = [row[1] for row in cursor.fetchall()]
    new_cols = [
        ('data_source', "TEXT DEFAULT 'Manual Entry'"),
        ('notes', "TEXT DEFAULT ''"),
        ('factor_source', "TEXT DEFAULT ''"),
        ('factor_version', "TEXT DEFAULT ''")
    ]
    for col_name, col_def in new_cols:
        if col_name not in columns:
            try:
                cursor.execute(f"ALTER TABLE emission_records ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS net_zero_targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
        baseline_emission REAL NOT NULL,
        target_emission REAL NOT NULL,
        target_reduction_percentage REAL NOT NULL,
        target_year INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emission_factors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        factor REAL NOT NULL,
        unit TEXT NOT NULL,
        factor_unit TEXT NOT NULL,
        scope TEXT NOT NULL,
        source TEXT NOT NULL,
        source_url TEXT,
        region TEXT,
        year TEXT,
        version TEXT,
        status TEXT DEFAULT 'Active',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scenarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
        name TEXT NOT NULL,
        target_year INTEGER NOT NULL,
        electricity_reduction_pct REAL NOT NULL DEFAULT 0.0,
        fuel_reduction_pct REAL NOT NULL DEFAULT 0.0,
        transport_reduction_pct REAL NOT NULL DEFAULT 0.0,
        baseline_co2e REAL NOT NULL,
        scenario_co2e REAL NOT NULL,
        annual_savings_co2e REAL NOT NULL,
        target_gap_co2e REAL NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS forecast_experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        dataset_type TEXT DEFAULT 'Historical Records',
        data_points INTEGER NOT NULL,
        train_points INTEGER NOT NULL,
        test_points INTEGER NOT NULL,
        split_cutoff TEXT NOT NULL,
        model_name TEXT NOT NULL,
        features TEXT NOT NULL,
        mae REAL NOT NULL,
        rmse REAL NOT NULL,
        r2 REAL,
        is_best INTEGER DEFAULT 0,
        evaluation_criterion TEXT DEFAULT 'Lowest RMSE',
        notes TEXT
    );
    ''')

    cursor.execute('SELECT id FROM users WHERE id = 1')
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (id, name, email) VALUES (1, 'Demo User', 'demo@example.com')")

    # Seed emission factors if empty
    cursor.execute('SELECT COUNT(*) as count FROM emission_factors')
    if cursor.fetchone()[0] == 0:
        json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'emission_factors.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    factor_data = json.load(f)
                    for cat, info in factor_data.items():
                        cursor.execute('''
                        INSERT OR IGNORE INTO emission_factors 
                        (category, name, factor, unit, factor_unit, scope, source, source_url, region, year, version, status, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            cat,
                            info.get('name', cat),
                            info.get('factor', 0.0),
                            info.get('unit', ''),
                            info.get('factor_unit', ''),
                            info.get('scope', 'Scope 1'),
                            info.get('source', ''),
                            info.get('source_url', ''),
                            info.get('region', ''),
                            info.get('year', ''),
                            info.get('version', ''),
                            info.get('status', 'Active'),
                            info.get('notes', '')
                        ))
            except Exception:
                pass

    conn.commit()
    conn.close()

def close_db(conn):
    if conn:
        conn.close()

def insert_emission_record(date, category, activity, unit, emission_factor, co2e, is_demo=0, 
                           data_source='Manual Entry', notes='', factor_source='', factor_version=''):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO emission_records 
           (date, category, activity, unit, emission_factor, co2e, is_demo, data_source, notes, factor_source, factor_version) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (date, category, activity, unit, emission_factor, co2e, is_demo, data_source, notes, factor_source, factor_version)
    )
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id

def update_emission_record(record_id, date, category, activity, unit, emission_factor, co2e, data_source='Manual Entry', notes=''):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''UPDATE emission_records 
           SET date = ?, category = ?, activity = ?, unit = ?, emission_factor = ?, co2e = ?, data_source = ?, notes = ?
           WHERE id = ?''',
        (date, category, activity, unit, emission_factor, co2e, data_source, notes, record_id)
    )
    conn.commit()
    conn.close()

def get_emission_by_id(record_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emission_records WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_emissions(category=None, month=None, date_from=None, date_to=None, is_demo=None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM emission_records WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    if month:
        query += " AND date = ?"
        params.append(month)
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    if is_demo is not None:
        query += " AND is_demo = ?"
        params.append(1 if is_demo else 0)
        
    query += " ORDER BY date DESC, id DESC"
    cursor.execute(query, params)
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return records

def delete_emission(record_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM emission_records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()

def get_emission_stats(date_from=None, date_to=None):
    conn = get_db()
    cursor = conn.cursor()
    
    where_clause = " WHERE 1=1"
    params = []
    if date_from:
        where_clause += " AND date >= ?"
        params.append(date_from)
    if date_to:
        where_clause += " AND date <= ?"
        params.append(date_to)

    cursor.execute(f"SELECT SUM(co2e) as total, COUNT(*) as count FROM emission_records{where_clause}", params)
    row = cursor.fetchone()
    total_emissions = row['total'] if row and row['total'] else 0.0
    total_count = row['count'] if row and row['count'] else 0

    cursor.execute(f"SELECT category, SUM(co2e) as total FROM emission_records{where_clause} GROUP BY category", params)
    category_breakdown = {r['category']: r['total'] for r in cursor.fetchall()}
    
    conn.close()
    return {
        'total_emissions': round(total_emissions, 4),
        'total_count': total_count,
        'category_breakdown': category_breakdown
    }

def get_monthly_emissions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT date as month, SUM(co2e) as total FROM emission_records GROUP BY date ORDER BY date")
    records = [{'month': row['month'], 'total': round(row['total'], 4)} for row in cursor.fetchall()]
    conn.close()
    return records

def get_category_emissions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT category, SUM(co2e) as total FROM emission_records GROUP BY category ORDER BY total DESC")
    records = [{'category': row['category'], 'total': round(row['total'], 4)} for row in cursor.fetchall()]
    conn.close()
    return records

def check_duplicate_record(date, category, activity, tolerance=0.001):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, date, category, activity, co2e FROM emission_records WHERE date = ? AND category = ? AND ABS(activity - ?) <= ?",
            (date, category, activity, tolerance)
        )
        duplicates = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return duplicates
    except sqlite3.OperationalError:
        return []

def insert_net_zero_target(baseline, target, reduction_pct, target_year):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO net_zero_targets (baseline_emission, target_emission, target_reduction_percentage, target_year) VALUES (?, ?, ?, ?)",
        (baseline, target, reduction_pct, target_year)
    )
    conn.commit()
    conn.close()

def get_latest_net_zero_target():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM net_zero_targets ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# Scenarios Persistence
def insert_scenario(name, target_year, elec_pct, fuel_pct, trans_pct, baseline_co2e, scenario_co2e, savings_co2e, gap_co2e, notes=''):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO scenarios 
           (name, target_year, electricity_reduction_pct, fuel_reduction_pct, transport_reduction_pct, 
            baseline_co2e, scenario_co2e, annual_savings_co2e, target_gap_co2e, notes) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (name, target_year, elec_pct, fuel_pct, trans_pct, baseline_co2e, scenario_co2e, savings_co2e, gap_co2e, notes)
    )
    scenario_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return scenario_id

def get_all_scenarios():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scenarios ORDER BY created_at DESC")
    records = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return records

def delete_scenario(scenario_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
    conn.commit()
    conn.close()

# Emission Factors Persistence
def get_all_emission_factors():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emission_factors ORDER BY scope, category")
    records = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return records

def get_emission_factor_by_category(category):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM emission_factors WHERE category = ?", (category,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# Forecast Experiments Persistence
def insert_forecast_experiment(run_dict):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO forecast_experiments 
           (dataset_type, data_points, train_points, test_points, split_cutoff, model_name, features, mae, rmse, r2, is_best, evaluation_criterion, notes) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            run_dict.get('dataset_type', 'Historical Records'),
            run_dict.get('data_points', 0),
            run_dict.get('train_points', 0),
            run_dict.get('test_points', 0),
            run_dict.get('split_cutoff', ''),
            run_dict.get('model_name', ''),
            run_dict.get('features', ''),
            run_dict.get('mae', 0.0),
            run_dict.get('rmse', 0.0),
            run_dict.get('r2'),
            1 if run_dict.get('is_best') else 0,
            run_dict.get('evaluation_criterion', 'Lowest RMSE'),
            run_dict.get('notes', '')
        )
    )
    exp_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return exp_id

def get_latest_forecast_experiments(dataset_type=None, limit=10):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM forecast_experiments"
    params = []
    if dataset_type:
        query += " WHERE dataset_type = ?"
        params.append(dataset_type)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, params)
    records = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return records

def load_demo_data(emission_factors=None):
    """Insert realistic demo records for Jan-Jun with is_demo=1.
    Uses fixed realistic values rather than random data for reproducibility."""
    from services.emission_calculator import load_emission_factors as get_factors
    if emission_factors is None:
        emission_factors = get_factors()

    demo_records = [
        # (month, category, activity, data_source, notes)
        ('2024-01', 'electricity', 210, 'Utility Bill', 'Academic Hall A heating & lighting'),
        ('2024-01', 'petrol', 32, 'Fuel Receipt', 'Department courier van'),
        ('2024-01', 'diesel', 15, 'Fuel Receipt', 'Emergency generator monthly load test'),
        ('2024-02', 'electricity', 240, 'Utility Bill', 'Academic Hall A computing labs'),
        ('2024-02', 'petrol', 38, 'Fuel Receipt', 'Field survey trip'),
        ('2024-02', 'diesel', 12, 'Fuel Receipt', 'Facility generator'),
        ('2024-03', 'electricity', 190, 'Utility Bill', 'Mid-term break low occupancy'),
        ('2024-03', 'petrol', 28, 'Fuel Receipt', 'Routine courier runs'),
        ('2024-03', 'transport_car_petrol', 120, 'Commute Survey', 'Staff vehicle commuting sample'),
        ('2024-04', 'electricity', 260, 'Utility Bill', 'Spring symposium high AC load'),
        ('2024-04', 'petrol', 41, 'Fuel Receipt', 'Student project vehicle travel'),
        ('2024-04', 'diesel', 18, 'Fuel Receipt', 'Generator maintenance test'),
        ('2024-05', 'electricity', 230, 'Utility Bill', 'Standard academic operations'),
        ('2024-05', 'petrol', 35, 'Fuel Receipt', 'Administrative transport'),
        ('2024-05', 'transport_bus', 200, 'Commute Survey', 'Faculty bus pass transit logs'),
        ('2024-06', 'electricity', 200, 'Utility Bill', 'Summer session partial occupancy'),
        ('2024-06', 'petrol', 30, 'Fuel Receipt', 'Administrative transport'),
        ('2024-06', 'transport_train', 150, 'Travel Log', 'Inter-university conference travel'),
    ]
    
    conn = get_db()
    cursor = conn.cursor()
    for month, cat, activity, src, notes in demo_records:
        factor_info = emission_factors.get(cat, {})
        factor = factor_info.get('factor', 1.0)
        unit = factor_info.get('unit', 'unit')
        factor_src = factor_info.get('source', 'Default Factor')
        factor_ver = factor_info.get('version', 'v1.0')
        co2e = round(activity * factor, 4)
        cursor.execute(
            '''INSERT INTO emission_records 
               (date, category, activity, unit, emission_factor, co2e, is_demo, data_source, notes, factor_source, factor_version) 
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)''',
            (month, cat, round(activity, 2), unit, factor, co2e, src, notes, factor_src, factor_ver)
        )
    conn.commit()
    conn.close()

def clear_demo_data():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM emission_records WHERE is_demo = 1")
    conn.commit()
    conn.close()

def clear_all_emissions():
    """Deletes all activity records from the inventory."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM emission_records")
    conn.commit()
    conn.close()

def get_emission_count():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM emission_records")
    row = cursor.fetchone()
    conn.close()
    return row['count']
