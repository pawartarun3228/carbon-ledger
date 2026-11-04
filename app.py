import os
import re
import io
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, jsonify, send_file, Response, session
)

from models.database import (
    init_db, get_all_emissions, insert_emission_record, 
    update_emission_record, get_emission_by_id,
    get_emission_stats, delete_emission, load_demo_data, 
    clear_demo_data, clear_all_emissions, get_latest_net_zero_target, 
    insert_net_zero_target, get_monthly_emissions, get_category_emissions,
    insert_scenario, get_all_scenarios, delete_scenario,
    get_all_emission_factors, check_duplicate_record,
    create_user, get_user_by_email, get_user_by_id,
    update_user_profile, update_user_password, update_user_last_login,
    create_password_reset, get_password_reset, mark_password_reset_used
)
from services.auth import (
    hash_password, verify_password, validate_password_strength,
    validate_email_format, generate_reset_token, verify_reset_token,
    hash_token, check_login_rate_limit, record_failed_login,
    reset_login_attempts, login_required
)
from services.emission_calculator import (
    get_available_categories, calculate_emission, 
    load_emission_factors, get_category_display_group
)
from services.factor_registry import (
    get_factor_registry, kg_to_tonnes, tonnes_to_kg
)
from services.data_validation import (
    validate_activity_entry, validate_csv_content, ALLOWED_DATA_SOURCES
)
from services.aggregation import aggregate_emissions
from services.recommendation_engine import generate_recommendations
from services.net_zero import calculate_net_zero_plan
from services.scenario_engine import simulate_decarbonization_scenario
from services.prediction import predict_next_month
from services.forecasting import (
    run_forecasting_experiment, generate_synthetic_benchmark_dataset,
    load_bdg2_benchmark_dataset
)
from services.anomaly_detector import detect_activity_anomalies
from services.report_generator import (
    generate_pdf_report, generate_csv_records_export, 
    generate_csv_monthly_summary, generate_csv_template
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'carbon_ledger_institutional_secret_key_2026')
app.config['ENFORCE_TEST_LOGIN'] = False

# Cookie security settings
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Initialize database schema and factor catalog on app startup
with app.app_context():
    init_db()

@app.context_processor
def inject_global_metadata():
    """Provides common variables and current authenticated user across templates."""
    user = None
    user_id = session.get('user_id')
    if user_id:
        user = get_user_by_id(user_id)
    return {
        'app_name': 'Carbon Ledger',
        'tagline': 'Measure emissions. Understand impact. Plan a lower-carbon future.',
        'allowed_sources': ALLOWED_DATA_SOURCES,
        'current_user': user
    }

# ----------------------------------------------------
# 1. Authentication & User Profile Routes
# ----------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Modern Minimalist Login Page (Inspired by ChatGPT aesthetics)."""
    if session.get('user_id'):
        return redirect(url_for('dashboard'))

    next_url = request.args.get('next', '')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me') == '1'
        client_ip = request.remote_addr or 'unknown'

        # Basic validations
        if not email or not password:
            flash('Both email address and password are required.', 'error')
            return render_template('auth/login.html', email=email)

        if not validate_email_format(email):
            flash('Please enter a valid email address.', 'error')
            return render_template('auth/login.html', email=email)

        # Rate limiting check against brute-force attacks
        rate_key = f"{client_ip}:{email}"
        allowed, retry_sec = check_login_rate_limit(rate_key)
        if not allowed:
            flash(f"Too many failed login attempts. For security, please wait {retry_sec} seconds before trying again.", 'error')
            return render_template('auth/login.html', email=email), 429

        user = get_user_by_email(email)
        if not user or not verify_password(user['password_hash'], password):
            record_failed_login(rate_key)
            flash('Invalid email address or password. Please try again.', 'error')
            return render_template('auth/login.html', email=email)

        if not user.get('is_active', 1):
            flash('This account is deactivated. Please contact support.', 'error')
            return render_template('auth/login.html', email=email)

        # Successful login
        reset_login_attempts(rate_key)
        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_email'] = user['email']
        if remember_me:
            session.permanent = True
        
        update_user_last_login(user['id'])
        flash(f"Welcome back, {user['name']}!", 'success')

        # Prevent open redirect vulnerabilities
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('dashboard'))

    return render_template('auth/login.html')

@app.route('/demo-login')
def demo_login():
    """Quick 1-click evaluation sign-in as Demo User (Green Horizon Institute)."""
    user = get_user_by_id(1)
    if not user:
        init_db()
        user = get_user_by_id(1)

    session.clear()
    session['user_id'] = 1
    session['user_name'] = user['name'] if user else 'Demo User'
    session['user_email'] = user['email'] if user else 'demo@example.com'
    update_user_last_login(1)
    flash('Signed in as Demo User (Green Horizon Institute). Explore the platform!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/google-demo-login')
def google_demo_login():
    """Simulates authenticated Google SSO profile for evaluation/demonstration."""
    email = 'alex.mercer.google@example.org'
    user = get_user_by_email(email)
    if not user:
        user_id = create_user(
            name='Dr. Alex Mercer',
            email=email,
            password_hash=hash_password('GoogleOAuthDemo@2026'),
            organisation_name='Apex University Clean Energy Research',
            organisation_type='University / Educational Institution',
            country='India',
            sector='Higher Education'
        )
    else:
        user_id = user['id']

    session.clear()
    session['user_id'] = user_id
    session['user_name'] = 'Dr. Alex Mercer'
    session['user_email'] = email
    update_user_last_login(user_id)
    flash('Authenticated via Google Workspace (Simulated Single Sign-On Profile).', 'success')
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """New Account Registration Page."""
    if session.get('user_id'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        org_name = request.form.get('organisation_name', '').strip()
        org_type = request.form.get('organisation_type', '').strip()

        # Validation
        if not name or not email or not password or not confirm_password:
            flash('All required fields must be completed.', 'error')
            return render_template('auth/register.html', name=name, email=email, 
                                   organisation_name=org_name, organisation_type=org_type)

        if not validate_email_format(email):
            flash('Please enter a valid institutional or personal email address.', 'error')
            return render_template('auth/register.html', name=name, email=email, 
                                   organisation_name=org_name, organisation_type=org_type)

        is_strong, err_msg = validate_password_strength(password)
        if not is_strong:
            flash(err_msg, 'error')
            return render_template('auth/register.html', name=name, email=email, 
                                   organisation_name=org_name, organisation_type=org_type)

        if password != confirm_password:
            flash('Passwords do not match. Please re-enter carefully.', 'error')
            return render_template('auth/register.html', name=name, email=email, 
                                   organisation_name=org_name, organisation_type=org_type)

        # Check duplicate registration
        if get_user_by_email(email):
            flash('An account with this email address already exists. Please sign in.', 'error')
            return render_template('auth/register.html', name=name, email=email, 
                                   organisation_name=org_name, organisation_type=org_type)

        # Hash password and persist user
        pw_hash = hash_password(password)
        user_id = create_user(
            name=name,
            email=email,
            password_hash=pw_hash,
            organisation_name=org_name,
            organisation_type=org_type
        )

        # Automatically sign user in
        session.clear()
        session['user_id'] = user_id
        session['user_name'] = name
        session['user_email'] = email
        update_user_last_login(user_id)

        flash('Your account has been created successfully! Welcome to Carbon Ledger.', 'success')
        # Redirect to organisation profile onboarding
        return redirect(url_for('onboarding'))

    return render_template('auth/register.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Password Recovery Workflow."""
    if session.get('user_id'):
        return redirect(url_for('dashboard'))

    reset_link = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email or not validate_email_format(email):
            flash('Please enter a valid email address.', 'error')
            return render_template('auth/forgot_password.html', email=email)

        user = get_user_by_email(email)
        token = generate_reset_token(email, secret_key=app.secret_key)

        if user:
            t_hash = hash_token(token)
            expires_at = (datetime.now() + timedelta(hours=1)).isoformat()
            create_password_reset(user['id'], t_hash, expires_at)

        # Check SMTP configuration
        mail_server = os.environ.get('MAIL_SERVER')
        if mail_server:
            # When SMTP is live, deliver email silently without revealing registration status
            flash('If an account exists with this email address, password reset instructions have been sent.', 'info')
            return redirect(url_for('login'))
        else:
            # Explicit academic & evaluator transparency: do not pretend SMTP succeeded
            flash('Password reset token generated. In this demo/development environment without SMTP credentials, use the evaluation link below:', 'info')
            reset_link = url_for('reset_password_route', token=token)
            return render_template('auth/forgot_password.html', email=email, reset_link=reset_link)

    return render_template('auth/forgot_password.html', reset_link=reset_link)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_route(token):
    """Secure Single-Use Password Reset Form."""
    if session.get('user_id'):
        return redirect(url_for('dashboard'))

    email = verify_reset_token(token, max_age=3600, secret_key=app.secret_key)
    if not email:
        flash('This password reset link is invalid or has expired. Please request a new one.', 'error')
        return redirect(url_for('forgot_password'))

    t_hash = hash_token(token)
    reset_rec = get_password_reset(t_hash)
    if not reset_rec or reset_rec.get('used'):
        flash('This password reset link has already been used or expired.', 'error')
        return redirect(url_for('forgot_password'))

    user = get_user_by_email(email)
    if not user:
        flash('Account not found.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        is_strong, err_msg = validate_password_strength(new_password)
        if not is_strong:
            flash(err_msg, 'error')
            return render_template('auth/reset_password.html', token=token, email=email)

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html', token=token, email=email)

        new_hash = hash_password(new_password)
        update_user_password(user['id'], new_hash)
        mark_password_reset_used(t_hash)

        flash('Password updated successfully! Please log in with your new credentials.', 'success')
        return redirect(url_for('login'))

    return render_template('auth/reset_password.html', token=token, email=email)

@app.route('/onboarding', methods=['GET', 'POST'])
@login_required
def onboarding():
    """Organisation Profile Onboarding Wizard."""
    user = get_user_by_id(session['user_id'])
    if request.method == 'POST':
        profile_data = {
            'organisation_name': request.form.get('organisation_name', '').strip(),
            'organisation_type': request.form.get('organisation_type', '').strip(),
            'country': request.form.get('country', '').strip(),
            'sector': request.form.get('sector', '').strip(),
            'org_size': request.form.get('org_size', '').strip(),
            'reporting_period': request.form.get('reporting_period', '').strip(),
            'electricity_source': request.form.get('electricity_source', '').strip()
        }
        update_user_profile(user['id'], profile_data)
        flash('Organisation profile updated successfully.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('auth/onboarding.html', user=user)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Account Settings & Organisation Profile Management."""
    user = get_user_by_id(session['user_id'])
    user_records = get_all_emissions(user_id=user['id'])
    user_co2e = sum(r['co2e'] for r in user_records)
    user_tonnes = kg_to_tonnes(user_co2e)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            name = request.form.get('name', '').strip()
            if not name:
                flash('Full name cannot be empty.', 'error')
                return redirect(url_for('profile'))

            profile_data = {
                'name': name,
                'organisation_name': request.form.get('organisation_name', '').strip(),
                'organisation_type': request.form.get('organisation_type', '').strip(),
                'country': request.form.get('country', '').strip(),
                'sector': request.form.get('sector', '').strip(),
                'org_size': request.form.get('org_size', '').strip(),
                'reporting_period': request.form.get('reporting_period', '').strip(),
                'electricity_source': request.form.get('electricity_source', '').strip()
            }
            update_user_profile(user['id'], profile_data)
            session['user_name'] = name
            flash('Profile details updated successfully.', 'success')
            return redirect(url_for('profile'))

        elif action == 'change_password':
            curr_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')

            if not verify_password(user['password_hash'], curr_pwd):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('profile'))

            is_strong, err_msg = validate_password_strength(new_pwd)
            if not is_strong:
                flash(err_msg, 'error')
                return redirect(url_for('profile'))

            if new_pwd != confirm_pwd:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('profile'))

            update_user_password(user['id'], hash_password(new_pwd))
            flash('Your password has been changed successfully.', 'success')
            return redirect(url_for('profile'))

    return render_template(
        'profile.html',
        user=user,
        user_records_count=len(user_records),
        user_tonnes=user_tonnes
    )

@app.route('/logout')
def logout():
    """Safely terminates user session and redirects to sign in."""
    session.clear()
    flash('You have been signed out successfully.', 'info')
    return redirect(url_for('login'))

# ----------------------------------------------------
# 2. Primary Application Pages (Protected)
# ----------------------------------------------------

@app.route('/')
def index():
    """Institutional UN-inspired Public Landing Page."""
    stats = get_emission_stats()
    all_records = get_all_emissions()
    factors = load_emission_factors()
    return render_template('index.html', 
                           total_emissions=stats['total_emissions'],
                           total_tonnes=kg_to_tonnes(stats['total_emissions']),
                           record_count=stats['total_count'],
                           factor_count=len(factors),
                           has_data=len(all_records) > 0)

@app.route('/dashboard')
@login_required
def dashboard():
    """Executive Sustainability Dashboard (User-Specific Inventory)."""
    user_id = session.get('user_id')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    all_records = get_all_emissions(user_id=user_id)
    agg = aggregate_emissions(all_records, date_from=date_from or None, date_to=date_to or None)
    
    target = get_latest_net_zero_target(user_id=user_id)
    reduction_progress = 0.0
    has_target = target is not None
    
    if has_target and target['baseline_emission'] > 0:
        required_reduction = target['baseline_emission'] - target['target_emission']
        if required_reduction > 0:
            reduction_achieved = target['baseline_emission'] - agg['total_kg']
            reduction_progress = max(0.0, min(100.0, (reduction_achieved / required_reduction) * 100.0))
        else:
            reduction_progress = 100.0

    recent_records = all_records[:8] if all_records else []

    return render_template(
        'dashboard.html',
        total_emissions=agg['total_kg'],
        total_tonnes=agg['total_tonnes'],
        electricity_emissions=agg['groups'].get('electricity', 0.0),
        fuel_emissions=agg['groups'].get('fuel', 0.0),
        transport_emissions=agg['groups'].get('transportation', 0.0),
        other_emissions=agg['groups'].get('other', 0.0),
        reduction_progress=round(reduction_progress, 1),
        highest_source=agg['highest_category'] or 'None',
        highest_source_pct=round(agg['highest_category_pct'], 1),
        has_data=len(all_records) > 0,
        has_target=has_target,
        target=target,
        recent_records=recent_records,
        warnings=agg['data_quality_warnings'],
        date_from=date_from,
        date_to=date_to
    )

@app.route('/add-data', methods=['GET', 'POST'])
@login_required
def add_data():
    """Manual Activity Entry Form."""
    user_id = session.get('user_id')
    categories = get_available_categories()
    if request.method == 'POST':
        date = request.form.get('date', '').strip()
        category = request.form.get('category', '').strip()
        activity_str = request.form.get('activity', '').strip()
        unit = request.form.get('unit', '').strip()
        data_source = request.form.get('data_source', 'Manual Entry').strip()
        notes = request.form.get('notes', '').strip()

        ok, result, err = validate_activity_entry(date, category, activity_str, unit, data_source, notes)
        if not ok:
            flash(err, 'error')
            return redirect(url_for('add_data'))

        try:
            calc_result = calculate_emission(result['category'], result['activity'], result['unit'])
            record_id = insert_emission_record(
                date=result['date'],
                category=result['category'],
                activity=result['activity'],
                unit=calc_result['calc_unit'],
                emission_factor=calc_result['emission_factor'],
                co2e=calc_result['co2e'],
                data_source=result['data_source'],
                notes=result['notes'],
                factor_source=calc_result['source'],
                factor_version=calc_result['version'],
                is_demo=0,
                user_id=user_id
            )
            if result.get('duplicate_warning'):
                flash(result['duplicate_warning'], 'warning')
            flash(f"Activity logged successfully! Calculated: {calc_result['co2e']} kg CO2e.", 'success')
            return redirect(url_for('history'))
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('add_data'))

    return render_template('add_data.html', categories=categories, sources=ALLOWED_DATA_SOURCES)

@app.route('/edit-data/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_data(id):
    """Edit an existing activity record."""
    user_id = session.get('user_id')
    record = get_emission_by_id(id, user_id=user_id)
    if not record:
        flash("Record not found or access restricted.", 'error')
        return redirect(url_for('history'))

    categories = get_available_categories()
    if request.method == 'POST':
        date = request.form.get('date', '').strip()
        category = request.form.get('category', '').strip()
        activity_str = request.form.get('activity', '').strip()
        unit = request.form.get('unit', '').strip()
        data_source = request.form.get('data_source', 'Manual Entry').strip()
        notes = request.form.get('notes', '').strip()

        ok, result, err = validate_activity_entry(date, category, activity_str, unit, data_source, notes)
        if not ok:
            flash(err, 'error')
            return render_template('edit_data.html', record=record, categories=categories, sources=ALLOWED_DATA_SOURCES)

        try:
            calc_result = calculate_emission(result['category'], result['activity'], result['unit'])
            update_emission_record(
                id,
                date=result['date'],
                category=result['category'],
                activity=result['activity'],
                unit=calc_result['calc_unit'],
                emission_factor=calc_result['emission_factor'],
                co2e=calc_result['co2e'],
                data_source=result['data_source'],
                notes=result['notes'],
                user_id=user_id
            )
            flash("Record updated successfully.", 'success')
            return redirect(url_for('history'))
        except ValueError as e:
            flash(str(e), 'error')

    return render_template('edit_data.html', record=record, categories=categories, sources=ALLOWED_DATA_SOURCES)

@app.route('/delete-data/<int:id>', methods=['POST'])
@login_required
def delete_record_route(id):
    """Deletes a specific activity record."""
    user_id = session.get('user_id')
    delete_emission(id, user_id=user_id)
    flash(f"Activity record #{id} removed.", 'info')
    return redirect(url_for('history'))

@app.route('/history')
@app.route('/activities')
@login_required
def history():
    """Activity Records Management with Filtering and CSV Import."""
    user_id = session.get('user_id')
    category = request.args.get('category')
    month = request.args.get('month')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    demo_filter = request.args.get('is_demo')
    
    is_demo_val = None
    if demo_filter == '1':
        is_demo_val = True
    elif demo_filter == '0':
        is_demo_val = False

    records = get_all_emissions(
        category=category or None, 
        month=month or None,
        date_from=date_from or None,
        date_to=date_to or None,
        is_demo=is_demo_val,
        user_id=user_id
    )
    categories = get_available_categories()
    
    total_co2e = sum(r['co2e'] for r in records)
    total_tonnes = kg_to_tonnes(total_co2e)
    anomaly_report = detect_activity_anomalies(records)

    return render_template(
        'history.html', 
        records=records, 
        categories=categories, 
        total_co2e=round(total_co2e, 2),
        total_tonnes=total_tonnes,
        anomaly_report=anomaly_report,
        selected_category=category or '', 
        selected_month=month or '',
        date_from=date_from or '',
        date_to=date_to or '',
        selected_demo=demo_filter or ''
    )

@app.route('/emission-factors')
def emission_factors_page():
    """Public Emission Factor Registry View."""
    factors = load_emission_factors()
    return render_template('emission_factors.html', factors=factors)

@app.route('/recommendations')
@login_required
def recommendations():
    """Explainable Recommendation Engine."""
    user_id = session.get('user_id')
    records = get_all_emissions(user_id=user_id)
    total_emissions = sum(r['co2e'] for r in records)
    recs = generate_recommendations(records)
    return render_template(
        'recommendations.html', 
        recommendations=recs, 
        total_emissions=round(total_emissions, 2),
        total_tonnes=kg_to_tonnes(total_emissions),
        has_data=len(records) > 0
    )

@app.route('/net-zero', methods=['GET', 'POST'])
@login_required
def net_zero():
    """Net-Zero Target and Scenario Planner."""
    user_id = session.get('user_id')

    if request.method == 'POST':
        action = request.form.get('action', 'set_target')
        
        if action == 'save_scenario':
            scenario_name = request.form.get('scenario_name', 'Custom Scenario').strip()
            target_year = int(request.form.get('scenario_target_year', 2030))
            elec_pct = float(request.form.get('sim_electricity', 0.0))
            fuel_pct = float(request.form.get('sim_fuel', 0.0))
            trans_pct = float(request.form.get('sim_transport', 0.0))
            baseline_val = float(request.form.get('sim_baseline', 0.0))
            notes = request.form.get('scenario_notes', '').strip()

            target = get_latest_net_zero_target(user_id=user_id)
            target_pct = target['target_reduction_percentage'] if target else 50.0

            stats = get_emission_stats(user_id=user_id)
            base_dict = {
                'electricity': sum(r['co2e'] for r in get_all_emissions(category='electricity', user_id=user_id)),
                'fuel': sum(r['co2e'] for r in get_all_emissions(user_id=user_id) if r['category'] in ('petrol', 'diesel')),
                'transportation': sum(r['co2e'] for r in get_all_emissions(user_id=user_id) if r['category'].startswith('transport_')),
                'other': 0.0
            }
            if baseline_val > 0:
                base_dict['electricity'] = baseline_val * (base_dict['electricity'] / max(1.0, stats['total_emissions']))
                base_dict['fuel'] = baseline_val * (base_dict['fuel'] / max(1.0, stats['total_emissions']))
                base_dict['transportation'] = baseline_val * (base_dict['transportation'] / max(1.0, stats['total_emissions']))

            sim_result = simulate_decarbonization_scenario(
                base_dict, target_pct, target_year, elec_pct, fuel_pct, trans_pct
            )

            insert_scenario(
                name=scenario_name,
                target_year=target_year,
                elec_pct=elec_pct,
                fuel_pct=fuel_pct,
                trans_pct=trans_pct,
                baseline_co2e=sim_result['baseline_total_kg'],
                scenario_co2e=sim_result['scenario_total_kg'],
                savings_co2e=sim_result['savings_kg'],
                gap_co2e=sim_result['remaining_gap_kg'],
                notes=notes,
                user_id=user_id
            )
            flash(f"Scenario '{scenario_name}' saved successfully!", 'success')
            return redirect(url_for('net_zero'))

        else:
            # Setting baseline and target
            try:
                baseline = float(request.form.get('baseline', 0))
                target_pct = float(request.form.get('target_pct', 0))
                target_year = int(request.form.get('target_year', 0))
                
                if baseline <= 0:
                    flash('Baseline emissions must be a positive number.', 'error')
                    return redirect(url_for('net_zero'))
                if not (0 < target_pct <= 100):
                    flash('Reduction percentage must be between 1 and 100.', 'error')
                    return redirect(url_for('net_zero'))
                
                target_emission = round(baseline * (1 - target_pct / 100), 2)
                insert_net_zero_target(baseline, target_emission, target_pct, target_year, user_id=user_id)
                flash('Net-zero target updated successfully!', 'success')
                return redirect(url_for('net_zero'))
            except (ValueError, TypeError):
                flash('Please enter valid numeric values.', 'error')
                return redirect(url_for('net_zero'))
        
    target = get_latest_net_zero_target(user_id=user_id)
    plan = None
    all_records = get_all_emissions(user_id=user_id)
    stats = get_emission_stats(user_id=user_id)
    current_emission = stats['total_emissions']
    
    if target:
        try:
            plan = calculate_net_zero_plan(
                target['baseline_emission'], 
                target['target_reduction_percentage'], 
                target['target_year'], 
                current_emission
            )
        except ValueError:
            plan = None

    # Compute baseline category breakdown for the interactive simulation
    elec_base = sum(r['co2e'] for r in all_records if r['category'] == 'electricity')
    fuel_base = sum(r['co2e'] for r in all_records if r['category'] in ('petrol', 'diesel'))
    trans_base = sum(r['co2e'] for r in all_records if r['category'].startswith('transport_'))
    other_base = max(0.0, current_emission - (elec_base + fuel_base + trans_base))

    base_emissions_dict = {
        'electricity': elec_base if elec_base > 0 else (target['baseline_emission'] * 0.55 if target else 1000.0),
        'fuel': fuel_base if fuel_base > 0 else (target['baseline_emission'] * 0.25 if target else 500.0),
        'transportation': trans_base if trans_base > 0 else (target['baseline_emission'] * 0.20 if target else 300.0),
        'other': other_base
    }

    sim_target_pct = target['target_reduction_percentage'] if target else 50.0
    sim_target_year = target['target_year'] if target else 2030
    simulation = simulate_decarbonization_scenario(
        base_emissions_dict, sim_target_pct, sim_target_year,
        elec_reduction_pct=20.0, fuel_reduction_pct=15.0, transport_reduction_pct=15.0
    )

    saved_scenarios = get_all_scenarios(user_id=user_id)

    return render_template(
        'net_zero.html', 
        plan=plan, 
        has_plan=target is not None, 
        target=target,
        current_emission=current_emission,
        simulation=simulation,
        saved_scenarios=saved_scenarios,
        base_dict=base_emissions_dict
    )

@app.route('/delete-scenario/<int:id>', methods=['POST'])
@login_required
def delete_scenario_route(id):
    """Deletes a saved decarbonization scenario."""
    user_id = session.get('user_id')
    delete_scenario(id, user_id=user_id)
    flash("Scenario removed.", 'info')
    return redirect(url_for('net_zero'))

@app.route('/prediction')
@app.route('/forecasting')
@login_required
def prediction():
    """Research and Machine-Learning Forecasting Lab."""
    user_id = session.get('user_id')
    records = get_all_emissions(user_id=user_id)
    pred_quick = predict_next_month(records)
    
    benchmark = request.args.get('benchmark', 'inventory')
    
    if benchmark == 'bdg2':
        bench_records = load_bdg2_benchmark_dataset()
        exp_result = run_forecasting_experiment(
            bench_records, 
            dataset_type='BDG2 Empirical Benchmark (Bear_education_Maryjane, 24 Mo)'
        )
    elif benchmark == 'synthetic':
        bench_records = generate_synthetic_benchmark_dataset(num_months=24)
        exp_result = run_forecasting_experiment(
            bench_records, 
            dataset_type='Synthetic Benchmark (24 Mo)'
        )
    else:
        exp_result = run_forecasting_experiment(
            records, 
            dataset_type='Historical Inventory Records'
        )

    return render_template(
        'prediction.html', 
        prediction=pred_quick, 
        experiment=exp_result,
        benchmark_mode=benchmark,
        use_synthetic=(benchmark == 'synthetic')
    )

@app.route('/reports')
@login_required
def reports_page():
    """Reporting Center & Audit Preview."""
    user_id = session.get('user_id')
    records = get_all_emissions(user_id=user_id)
    agg = aggregate_emissions(records)
    target = get_latest_net_zero_target(user_id=user_id)
    recs = generate_recommendations(records)
    scenarios = get_all_scenarios(user_id=user_id)
    
    return render_template(
        'reports.html',
        records=records,
        aggregation=agg,
        target=target,
        recommendations=recs,
        scenarios=scenarios
    )

@app.route('/reports/download-pdf')
@login_required
def download_pdf():
    """Downloads formal sustainability inventory PDF report."""
    user_id = session.get('user_id')
    records = get_all_emissions(user_id=user_id)
    agg = aggregate_emissions(records)
    target = get_latest_net_zero_target(user_id=user_id)
    recs = generate_recommendations(records)
    scenarios = get_all_scenarios(user_id=user_id)
    
    exp_result = run_forecasting_experiment(records)
    
    pdf_buffer = generate_pdf_report({
        'records': records,
        'aggregation': agg,
        'target': target,
        'recommendations': recs,
        'scenarios': scenarios,
        'forecast': exp_result
    })
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="Carbon_Ledger_Sustainability_Report.pdf",
        mimetype="application/pdf"
    )

@app.route('/reports/download-csv')
@login_required
def download_csv_records():
    """Downloads detailed activity records as CSV."""
    user_id = session.get('user_id')
    records = get_all_emissions(user_id=user_id)
    csv_str = generate_csv_records_export(records)
    return Response(
        csv_str,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=carbon_ledger_activities.csv"}
    )

@app.route('/reports/download-monthly-csv')
@login_required
def download_csv_monthly():
    """Downloads aggregated monthly emissions as CSV."""
    user_id = session.get('user_id')
    records = get_all_emissions(user_id=user_id)
    agg = aggregate_emissions(records)
    csv_str = generate_csv_monthly_summary(agg['monthly_series'])
    return Response(
        csv_str,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=carbon_ledger_monthly_summary.csv"}
    )

@app.route('/download-template')
def download_template():
    """Downloads CSV upload template with guidance rows."""
    tmpl = generate_csv_template()
    return Response(
        tmpl,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=carbon_activity_upload_template.csv"}
    )

@app.route('/upload-csv', methods=['POST'])
@login_required
def upload_csv():
    """Handles bulk CSV activity data upload with validation."""
    user_id = session.get('user_id')
    if 'file' not in request.files:
        flash("No file part provided in upload.", 'error')
        return redirect(url_for('history'))
        
    file = request.files['file']
    if file.filename == '':
        flash("No file selected for upload.", 'error')
        return redirect(url_for('history'))

    if not file.filename.lower().endswith('.csv'):
        flash("Only .csv files are supported.", 'error')
        return redirect(url_for('history'))

    try:
        content = file.read().decode('utf-8-sig', errors='replace')
        valid_rows, errors, warnings = validate_csv_content(content)
        
        if errors:
            flash(f"CSV import failed with {len(errors)} error(s): {errors[0]}", 'error')
            return redirect(url_for('history'))

        if not valid_rows:
            flash("No valid activity records found in CSV.", 'warning')
            return redirect(url_for('history'))

        inserted_count = 0
        for r in valid_rows:
            calc = calculate_emission(r['category'], r['activity'], r['unit'])
            insert_emission_record(
                date=r['date'],
                category=r['category'],
                activity=r['activity'],
                unit=calc['calc_unit'],
                emission_factor=calc['emission_factor'],
                co2e=calc['co2e'],
                data_source=r['data_source'],
                notes=r['notes'],
                factor_source=calc['source'],
                factor_version=calc['version'],
                is_demo=0,
                user_id=user_id
            )
            inserted_count += 1

        msg = f"Successfully imported {inserted_count} activity records from CSV."
        if warnings:
            msg += f" Note: {len(warnings)} duplicate warning(s) flagged."
        flash(msg, 'success')
        return redirect(url_for('history'))
    except Exception as e:
        flash(f"Error processing CSV: {str(e)}", 'error')
        return redirect(url_for('history'))

@app.route('/methodology', endpoint='methodology')
def methodology_page():
    """Research Methodology & Project Documentation."""
    factors = load_emission_factors()
    return render_template('methodology.html', factors=factors)

# ----------------------------------------------------
# 3. JSON APIs
# ----------------------------------------------------

@app.route('/api/emissions', methods=['GET'])
def api_emissions():
    """Returns all emission records (user-aware)."""
    user_id = session.get('user_id')
    return jsonify({'records': get_all_emissions(user_id=user_id)})

@app.route('/api/inventory-summary', methods=['GET'])
def api_inventory_summary():
    """Returns organizational inventory summary, scope distributions, and net-zero progress."""
    user_id = session.get('user_id')
    records = get_all_emissions(user_id=user_id)
    stats = get_emission_stats(user_id=user_id)
    agg = aggregate_emissions(records)
    target = get_latest_net_zero_target(user_id=user_id)
    
    scope_breakdown = {
        'scope_1_kg': round(sum(r['co2e'] for r in records if r.get('scope') == 'Scope 1' or r.get('category') in ('petrol', 'diesel')), 2),
        'scope_2_kg': round(sum(r['co2e'] for r in records if r.get('scope') == 'Scope 2' or r.get('category') == 'electricity'), 2),
        'scope_3_kg': round(sum(r['co2e'] for r in records if r.get('scope') == 'Scope 3' or str(r.get('category')).startswith('transport_')), 2)
    }
    
    anomaly_res = detect_activity_anomalies(records)
    
    return jsonify({
        'total_records': len(records),
        'total_emissions_kg': stats['total_emissions'],
        'total_emissions_tonnes': kg_to_tonnes(stats['total_emissions']),
        'period_months': len(agg.get('monthly_series', [])),
        'highest_emitting_category': stats.get('highest_category', 'None'),
        'scopes': scope_breakdown,
        'has_net_zero_target': target is not None,
        'target_summary': {
            'target_year': target['target_year'] if target else None,
            'target_reduction_pct': target['target_reduction_percentage'] if target else None,
            'baseline_emission_kg': target['baseline_emission'] if target else None,
            'target_allowance_kg': target['target_emission'] if target else None
        } if target else None,
        'audit_anomalies_flagged': anomaly_res['anomalies_flagged']
    })

@app.route('/api/anomalies', methods=['GET'])
def api_anomalies():
    """Returns AI-screened activity anomalies requiring audit review."""
    user_id = session.get('user_id')
    records = get_all_emissions(user_id=user_id)
    return jsonify(detect_activity_anomalies(records))

@app.route('/api/monthly-emissions', methods=['GET'])
def api_monthly_emissions():
    """Returns monthly totals for Chart.js."""
    user_id = session.get('user_id')
    data = get_monthly_emissions(user_id=user_id)
    labels = [d['month'] for d in data]
    values = [d['total'] for d in data]
    return jsonify({'labels': labels, 'data': values})

@app.route('/api/category-emissions', methods=['GET'])
def api_category_emissions():
    """Returns category breakdown for Chart.js."""
    user_id = session.get('user_id')
    data = get_category_emissions(user_id=user_id)
    total = sum(d['total'] for d in data)
    labels = [d['category'] for d in data]
    values = [d['total'] for d in data]
    pcts = [(v/total * 100) if total > 0 else 0 for v in values]
    return jsonify({'labels': labels, 'data': values, 'percentages': pcts})

@app.route('/api/calculate', methods=['POST'])
def api_calculate():
    """Calculates emission for given category and activity quantity."""
    data = request.json or {}
    try:
        category = data.get('category')
        activity = float(data.get('activity', 0))
        unit = data.get('unit')
        res = calculate_emission(category, activity, unit)
        return jsonify(res)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/emissions/<int:id>', methods=['DELETE'])
@login_required
def api_delete_emission(id):
    """Deletes an emission record via API."""
    user_id = session.get('user_id')
    delete_emission(id, user_id=user_id)
    return jsonify({'success': True})

@app.route('/api/load-demo-data', methods=['POST'])
@login_required
def load_demo():
    """Loads standardized demonstration records for current user."""
    user_id = session.get('user_id')
    load_demo_data(user_id=user_id)
    flash('Demonstration dataset loaded: 18 records across Scopes 1, 2, and 3.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/api/clear-demo-data', methods=['POST'])
@login_required
def clear_demo():
    """Removes synthetic demo records while keeping user records intact."""
    user_id = session.get('user_id')
    clear_demo_data(user_id=user_id)
    flash('Demonstration records cleared from the active database.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/clear-all-data', methods=['POST'])
@app.route('/api/clear-all-data', methods=['POST'])
@login_required
def clear_all_data():
    """Deletes all activity records from the inventory for current user."""
    user_id = session.get('user_id')
    clear_all_emissions(user_id=user_id)
    flash('All activity records have been cleared from your inventory.', 'info')
    return redirect(url_for('history'))

@app.route('/api/simulate-scenario', methods=['POST'])
def api_simulate_scenario():
    """Interactive simulation recalculation endpoint."""
    data = request.json or {}
    try:
        base_dict = data.get('base_dict', {})
        target_pct = float(data.get('target_pct', 50.0))
        target_year = int(data.get('target_year', 2030))
        elec_r = float(data.get('elec_reduction', 0.0))
        fuel_r = float(data.get('fuel_reduction', 0.0))
        trans_r = float(data.get('transport_reduction', 0.0))

        sim = simulate_decarbonization_scenario(
            base_dict, target_pct, target_year, elec_r, fuel_r, trans_r
        )
        return jsonify(sim)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
