import sqlite3
import os
import json
from services.auth import hash_password

def get_db_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.db')

def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Users Table with Authentication & Organisation Profile Fields
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        organisation_name TEXT DEFAULT '',
        organisation_type TEXT DEFAULT '',
        country TEXT DEFAULT '',
        sector TEXT DEFAULT '',
        org_size TEXT DEFAULT '',
        reporting_period TEXT DEFAULT '',
        electricity_source TEXT DEFAULT '',
        is_active INTEGER DEFAULT 1,
        last_login TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    # Safe Schema Migration for users table
    cursor.execute("PRAGMA table_info(users)")
    existing_user_cols = [row[1] for row in cursor.fetchall()]
    user_migration_cols = [
        ('password_hash', "TEXT DEFAULT ''"),
        ('organisation_name', "TEXT DEFAULT ''"),
        ('organisation_type', "TEXT DEFAULT ''"),
        ('country', "TEXT DEFAULT ''"),
        ('sector', "TEXT DEFAULT ''"),
        ('org_size', "TEXT DEFAULT ''"),
        ('reporting_period', "TEXT DEFAULT ''"),
        ('electricity_source', "TEXT DEFAULT ''"),
        ('is_active', "INTEGER DEFAULT 1"),
        ('last_login', "TIMESTAMP")
    ]
    for col_name, col_def in user_migration_cols:
        if col_name not in existing_user_cols:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass

    # 2. Password Reset Tokens Table (Single-use, time-limited)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token_hash TEXT NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    ''')

    # 3. Emission Records Table
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
        ('user_id', "INTEGER DEFAULT 1"),
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

    # 4. Net Zero Targets Table
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

    cursor.execute("PRAGMA table_info(net_zero_targets)")
    nzt_cols = [row[1] for row in cursor.fetchall()]
    if 'user_id' not in nzt_cols:
        try:
            cursor.execute("ALTER TABLE net_zero_targets ADD COLUMN user_id INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

    # 5. Emission Factors Catalog Table
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

    # 6. Scenarios Table
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

    cursor.execute("PRAGMA table_info(scenarios)")
    scen_cols = [row[1] for row in cursor.fetchall()]
    if 'user_id' not in scen_cols:
        try:
            cursor.execute("ALTER TABLE scenarios ADD COLUMN user_id INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass

    # 7. Forecast Experiments Table
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

    # Seed or update Demo User (id = 1)
    cursor.execute('SELECT * FROM users WHERE id = 1')
    demo_user = cursor.fetchone()
    demo_pw_hash = hash_password('Demo@1234')
    if not demo_user:
        cursor.execute('''
            INSERT INTO users (id, name, email, password_hash, organisation_name, organisation_type, country, sector, org_size, reporting_period, electricity_source) 
            VALUES (1, 'Demo User', 'demo@example.com', ?, 'Green Horizon Institute', 'University / Educational Institution', 'India', 'Higher Education', '201-1000', 'Calendar Year (Jan-Dec)', 'Grid & Solar On-site')
        ''', (demo_pw_hash,))
    else:
        # If password hash is empty, populate default demo hash
        if not demo_user['password_hash']:
            cursor.execute('''
                UPDATE users SET 
                    password_hash = ?,
                    organisation_name = COALESCE(NULLIF(organisation_name, ''), 'Green Horizon Institute'),
                    organisation_type = COALESCE(NULLIF(organisation_type, ''), 'University / Educational Institution'),
                    country = COALESCE(NULLIF(country, ''), 'India'),
                    sector = COALESCE(NULLIF(sector, ''), 'Higher Education'),
                    org_size = COALESCE(NULLIF(org_size, ''), '201-1000'),
                    reporting_period = COALESCE(NULLIF(reporting_period, ''), 'Calendar Year (Jan-Dec)'),
                    electricity_source = COALESCE(NULLIF(electricity_source, ''), 'Grid & Solar On-site')
                WHERE id = 1
            ''', (demo_pw_hash,))

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

# ----------------------------------------------------
# User Management & Authentication Queries
# ----------------------------------------------------

def create_user(name: str, email: str, password_hash: str, 
                organisation_name: str = '', organisation_type: str = '',
                country: str = '', sector: str = '', org_size: str = '',
                reporting_period: str = '', electricity_source: str = '') -> int:
    """Creates a new registered user in the database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (
            name, email, password_hash, organisation_name, organisation_type,
            country, sector, org_size, reporting_period, electricity_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        name.strip(), email.strip().lower(), password_hash,
        organisation_name.strip(), organisation_type.strip(),
        country.strip(), sector.strip(), org_size.strip(),
        reporting_period.strip(), electricity_source.strip()
    ))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id

def get_user_by_email(email: str):
    """Retrieve user dictionary by case-insensitive email."""
    if not email:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: int):
    """Retrieve user dictionary by integer ID."""
    if not user_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_user_profile(user_id: int, profile_data: dict):
    """Updates organisation details and name for a user."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET
            name = COALESCE(?, name),
            organisation_name = COALESCE(?, organisation_name),
            organisation_type = COALESCE(?, organisation_type),
            country = COALESCE(?, country),
            sector = COALESCE(?, sector),
            org_size = COALESCE(?, org_size),
            reporting_period = COALESCE(?, reporting_period),
            electricity_source = COALESCE(?, electricity_source)
        WHERE id = ?
    ''', (
        profile_data.get('name'),
        profile_data.get('organisation_name'),
        profile_data.get('organisation_type'),
        profile_data.get('country'),
        profile_data.get('sector'),
        profile_data.get('org_size'),
        profile_data.get('reporting_period'),
        profile_data.get('electricity_source'),
        user_id
    ))
    conn.commit()
    conn.close()

def update_user_password(user_id: int, new_password_hash: str):
    """Updates user password hash."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password_hash, user_id))
    conn.commit()
    conn.close()

def update_user_last_login(user_id: int):
    """Records the timestamp of successful authentication."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def create_password_reset(user_id: int, token_hash: str, expires_at: str):
    """Stores a single-use password reset token hash."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO password_resets (user_id, token_hash, expires_at, used) VALUES (?, ?, ?, 0)",
        (user_id, token_hash, expires_at)
    )
    conn.commit()
    conn.close()

def get_password_reset(token_hash: str):
    """Finds an unused, active password reset token by its hash."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM password_resets WHERE token_hash = ? AND used = 0",
        (token_hash,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def mark_password_reset_used(token_hash: str):
    """Marks a password reset token as redeemed."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE password_resets SET used = 1 WHERE token_hash = ?", (token_hash,))
    conn.commit()
    conn.close()

# ----------------------------------------------------
# Emission Records Queries (Multi-User Aware)
# ----------------------------------------------------

def insert_emission_record(date, category, activity, unit, emission_factor, co2e, is_demo=0, 
                           data_source='Manual Entry', notes='', factor_source='', factor_version='', user_id=1):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO emission_records 
           (user_id, date, category, activity, unit, emission_factor, co2e, is_demo, data_source, notes, factor_source, factor_version) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (user_id or 1, date, category, activity, unit, emission_factor, co2e, is_demo, data_source, notes, factor_source, factor_version)
    )
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id

def update_emission_record(record_id, date, category, activity, unit, emission_factor, co2e, data_source='Manual Entry', notes='', user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = '''UPDATE emission_records 
               SET date = ?, category = ?, activity = ?, unit = ?, emission_factor = ?, co2e = ?, data_source = ?, notes = ?
               WHERE id = ?'''
    params = [date, category, activity, unit, emission_factor, co2e, data_source, notes, record_id]
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
        
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def get_emission_by_id(record_id, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM emission_records WHERE id = ?"
    params = [record_id]
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_emissions(category=None, month=None, date_from=None, date_to=None, is_demo=None, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM emission_records WHERE 1=1"
    params = []
    
    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)
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

def delete_emission(record_id, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = "DELETE FROM emission_records WHERE id = ?"
    params = [record_id]
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def get_emission_stats(date_from=None, date_to=None, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    
    where_clause = " WHERE 1=1"
    params = []
    if user_id is not None:
        where_clause += " AND user_id = ?"
        params.append(user_id)
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

def get_monthly_emissions(user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT date as month, SUM(co2e) as total FROM emission_records"
    params = []
    if user_id is not None:
        query += " WHERE user_id = ?"
        params.append(user_id)
    query += " GROUP BY date ORDER BY date"
    cursor.execute(query, params)
    records = [{'month': row['month'], 'total': round(row['total'], 4)} for row in cursor.fetchall()]
    conn.close()
    return records

def get_category_emissions(user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT category, SUM(co2e) as total FROM emission_records"
    params = []
    if user_id is not None:
        query += " WHERE user_id = ?"
        params.append(user_id)
    query += " GROUP BY category ORDER BY total DESC"
    cursor.execute(query, params)
    records = [{'category': row['category'], 'total': round(row['total'], 4)} for row in cursor.fetchall()]
    conn.close()
    return records

def check_duplicate_record(date, category, activity, tolerance=0.001, user_id=None):
    try:
        conn = get_db()
        cursor = conn.cursor()
        query = "SELECT id, date, category, activity, co2e FROM emission_records WHERE date = ? AND category = ? AND ABS(activity - ?) <= ?"
        params = [date, category, activity, tolerance]
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        cursor.execute(query, params)
        duplicates = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return duplicates
    except sqlite3.OperationalError:
        return []

# ----------------------------------------------------
# Net-Zero Targets & Scenarios (Multi-User Aware)
# ----------------------------------------------------

def insert_net_zero_target(baseline, target, reduction_pct, target_year, user_id=1):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO net_zero_targets (user_id, baseline_emission, target_emission, target_reduction_percentage, target_year) VALUES (?, ?, ?, ?, ?)",
        (user_id or 1, baseline, target, reduction_pct, target_year)
    )
    conn.commit()
    conn.close()

def get_latest_net_zero_target(user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    if user_id is not None:
        cursor.execute("SELECT * FROM net_zero_targets WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
        row = cursor.fetchone()
        if not row and user_id != 1:
            # Fall back to global/demo target if user hasn't configured custom target yet
            cursor.execute("SELECT * FROM net_zero_targets ORDER BY created_at DESC LIMIT 1")
            row = cursor.fetchone()
    else:
        cursor.execute("SELECT * FROM net_zero_targets ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def insert_scenario(name, target_year, elec_pct, fuel_pct, trans_pct, baseline_co2e, scenario_co2e, savings_co2e, gap_co2e, notes='', user_id=1):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO scenarios 
           (user_id, name, target_year, electricity_reduction_pct, fuel_reduction_pct, transport_reduction_pct, 
            baseline_co2e, scenario_co2e, annual_savings_co2e, target_gap_co2e, notes) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (user_id or 1, name, target_year, elec_pct, fuel_pct, trans_pct, baseline_co2e, scenario_co2e, savings_co2e, gap_co2e, notes)
    )
    scenario_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return scenario_id

def get_all_scenarios(user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM scenarios"
    params = []
    if user_id is not None:
        query += " WHERE user_id = ?"
        params.append(user_id)
    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)
    records = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return records

def delete_scenario(scenario_id, user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = "DELETE FROM scenarios WHERE id = ?"
    params = [scenario_id]
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    cursor.execute(query, params)
    conn.commit()
    conn.close()

# ----------------------------------------------------
# Emission Factors & Forecast Experiments
# ----------------------------------------------------

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

def load_demo_data(emission_factors=None, user_id=1):
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
               (user_id, date, category, activity, unit, emission_factor, co2e, is_demo, data_source, notes, factor_source, factor_version) 
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)''',
            (user_id or 1, month, cat, round(activity, 2), unit, factor, co2e, src, notes, factor_src, factor_ver)
        )
    conn.commit()
    conn.close()

def clear_demo_data(user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = "DELETE FROM emission_records WHERE is_demo = 1"
    params = []
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def clear_all_emissions(user_id=None):
    """Deletes activity records from the inventory."""
    conn = get_db()
    cursor = conn.cursor()
    query = "DELETE FROM emission_records"
    params = []
    if user_id:
        query += " WHERE user_id = ?"
        params.append(user_id)
    cursor.execute(query, params)
    conn.commit()
    conn.close()

def get_emission_count(user_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT COUNT(*) as count FROM emission_records"
    params = []
    if user_id:
        query += " WHERE user_id = ?"
        params.append(user_id)
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    return row['count']
