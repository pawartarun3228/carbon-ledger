import os
import re
import io
from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, jsonify, send_file, Response
)

from models.database import (
    init_db, get_all_emissions, insert_emission_record, 
    update_emission_record, get_emission_by_id,
    get_emission_stats, delete_emission, load_demo_data, 
    clear_demo_data, clear_all_emissions, get_latest_net_zero_target, 
    insert_net_zero_target, get_monthly_emissions, get_category_emissions,
    insert_scenario, get_all_scenarios, delete_scenario,
    get_all_emission_factors, check_duplicate_record
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

# Initialize database schema and factor catalog on app startup (supports both Gunicorn and direct launch)
with app.app_context():
    init_db()

@app.context_processor
def inject_global_metadata():
    """Provides common variables across templates."""
    return {
        'app_name': 'Carbon Ledger',
        'tagline': 'Measure emissions. Understand impact. Plan a lower-carbon future.',
        'allowed_sources': ALLOWED_DATA_SOURCES
    }

# ----------------------------------------------------
# 1. Primary Pages
# ----------------------------------------------------

@app.route('/')
def index():
    """Institutional UN-inspired Landing Page."""
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
def dashboard():
    """Executive Sustainability Dashboard."""
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    all_records = get_all_emissions()
    agg = aggregate_emissions(all_records, date_from=date_from or None, date_to=date_to or None)
    
    target = get_latest_net_zero_target()
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
def add_data():
    """Manual Activity Entry Form."""
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
                is_demo=0
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
def edit_data(id):
    """Edit an existing activity record."""
    record = get_emission_by_id(id)
    if not record:
        flash("Record not found.", 'error')
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
                notes=result['notes']
            )
            flash("Record updated successfully.", 'success')
            return redirect(url_for('history'))
        except ValueError as e:
            flash(str(e), 'error')

    return render_template('edit_data.html', record=record, categories=categories, sources=ALLOWED_DATA_SOURCES)

@app.route('/delete-data/<int:id>', methods=['POST'])
def delete_record_route(id):
    """Deletes a specific activity record."""
    delete_emission(id)
    flash(f"Activity record #{id} removed.", 'info')
    return redirect(url_for('history'))

@app.route('/history')
@app.route('/activities')
def history():
    """Activity Records Management with Filtering and CSV Import."""
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
        is_demo=is_demo_val
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
    """Emission Factor Registry View."""
    factors = load_emission_factors()
    return render_template('emission_factors.html', factors=factors)

@app.route('/recommendations')
def recommendations():
    """Explainable Recommendation Engine."""
    records = get_all_emissions()
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
def net_zero():
    """Net-Zero Target and Scenario Planner."""
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

            target = get_latest_net_zero_target()
            target_pct = target['target_reduction_percentage'] if target else 50.0

            stats = get_emission_stats()
            # If baseline not set, calculate from breakdown
            base_dict = {
                'electricity': sum(r['co2e'] for r in get_all_emissions(category='electricity')),
                'fuel': sum(r['co2e'] for r in get_all_emissions() if r['category'] in ('petrol', 'diesel')),
                'transportation': sum(r['co2e'] for r in get_all_emissions() if r['category'].startswith('transport_')),
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
                notes=notes
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
                insert_net_zero_target(baseline, target_emission, target_pct, target_year)
                flash('Net-zero target updated successfully!', 'success')
                return redirect(url_for('net_zero'))
            except (ValueError, TypeError):
                flash('Please enter valid numeric values.', 'error')
                return redirect(url_for('net_zero'))
        
    target = get_latest_net_zero_target()
    plan = None
    all_records = get_all_emissions()
    stats = get_emission_stats()
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

    # Default simulation run
    sim_target_pct = target['target_reduction_percentage'] if target else 50.0
    sim_target_year = target['target_year'] if target else 2030
    simulation = simulate_decarbonization_scenario(
        base_emissions_dict, sim_target_pct, sim_target_year,
        elec_reduction_pct=20.0, fuel_reduction_pct=15.0, transport_reduction_pct=15.0
    )

    saved_scenarios = get_all_scenarios()

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
def delete_scenario_route(id):
    """Deletes a saved decarbonization scenario."""
    delete_scenario(id)
    flash("Scenario removed.", 'info')
    return redirect(url_for('net_zero'))

@app.route('/prediction')
@app.route('/forecasting')
def prediction():
    """Research and Machine-Learning Forecasting Lab."""
    records = get_all_emissions()
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
def reports_page():
    """Reporting Center & Audit Preview."""
    records = get_all_emissions()
    agg = aggregate_emissions(records)
    target = get_latest_net_zero_target()
    recs = generate_recommendations(records)
    scenarios = get_all_scenarios()
    
    return render_template(
        'reports.html',
        records=records,
        aggregation=agg,
        target=target,
        recommendations=recs,
        scenarios=scenarios
    )

@app.route('/reports/download-pdf')
def download_pdf():
    """Downloads formal sustainability inventory PDF report."""
    records = get_all_emissions()
    agg = aggregate_emissions(records)
    target = get_latest_net_zero_target()
    recs = generate_recommendations(records)
    scenarios = get_all_scenarios()
    
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
def download_csv_records():
    """Downloads detailed activity records as CSV."""
    records = get_all_emissions()
    csv_str = generate_csv_records_export(records)
    return Response(
        csv_str,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=carbon_ledger_activities.csv"}
    )

@app.route('/reports/download-monthly-csv')
def download_csv_monthly():
    """Downloads aggregated monthly emissions as CSV."""
    records = get_all_emissions()
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
def upload_csv():
    """Handles bulk CSV activity data upload with validation."""
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
                is_demo=0
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

@app.route('/methodology')
def methodology_page():
    """Research Methodology & Project Documentation."""
    factors = load_emission_factors()
    return render_template('methodology.html', factors=factors)

# ----------------------------------------------------
# 2. JSON APIs
# ----------------------------------------------------

@app.route('/api/emissions', methods=['GET'])
def api_emissions():
    """Returns all emission records."""
    return jsonify({'records': get_all_emissions()})

@app.route('/api/inventory-summary', methods=['GET'])
def api_inventory_summary():
    """Returns organizational inventory summary, scope distributions, and net-zero progress."""
    records = get_all_emissions()
    stats = get_emission_stats()
    agg = aggregate_emissions(records)
    target = get_latest_net_zero_target()
    
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
    records = get_all_emissions()
    return jsonify(detect_activity_anomalies(records))

@app.route('/api/monthly-emissions', methods=['GET'])
def api_monthly_emissions():
    """Returns monthly totals for Chart.js."""
    data = get_monthly_emissions()
    labels = [d['month'] for d in data]
    values = [d['total'] for d in data]
    return jsonify({'labels': labels, 'data': values})

@app.route('/api/category-emissions', methods=['GET'])
def api_category_emissions():
    """Returns category breakdown for Chart.js."""
    data = get_category_emissions()
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
def api_delete_emission(id):
    """Deletes an emission record via API."""
    delete_emission(id)
    return jsonify({'success': True})

@app.route('/api/load-demo-data', methods=['POST'])
def load_demo():
    """Loads standardized demonstration records."""
    load_demo_data()
    flash('Demonstration dataset loaded: 18 months (Jan 2023 - Jun 2024, 72 records across Scopes 1, 2, and 3 for an academic department facility).', 'success')
    return redirect(url_for('dashboard'))

@app.route('/api/clear-demo-data', methods=['POST'])
def clear_demo():
    """Removes synthetic demo records while keeping user records intact."""
    clear_demo_data()
    flash('Demonstration records cleared from the active database.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/clear-all-data', methods=['POST'])
@app.route('/api/clear-all-data', methods=['POST'])
def clear_all_data():
    """Deletes all activity records from the inventory."""
    clear_all_emissions()
    flash('All activity records have been cleared from the inventory.', 'info')
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
