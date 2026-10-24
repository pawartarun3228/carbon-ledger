"""Automated Test Suite for Carbon Ledger Comprehensive Capabilities.
Validates:
- Known calculation examples & precision
- Zero, negative, non-finite, and unit mismatch rejection
- Factor source provenance and version traceability
- CSV parsing, row-level validation, and duplicate detection
- Scenarios and experiments persistence
- Scenario recalculation and trajectory glide paths
- Machine learning forecasting, chronological holdout, and leakage safeguards
- PDF and CSV report generation
- Complete HTTP endpoint routing and response codes
"""

import pytest
import os
import sys
import io
import tempfile
import numpy as np

# Ensure root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.database import (
    init_db, get_db, get_db_path, insert_emission_record, 
    get_all_emissions, insert_scenario, get_all_scenarios, 
    delete_scenario, insert_forecast_experiment, get_latest_forecast_experiments,
    check_duplicate_record
)
from services.emission_calculator import calculate_emission, load_emission_factors
from services.factor_registry import (
    get_factor_registry, validate_unit_compatibility, 
    normalize_unit_conversion, kg_to_tonnes, tonnes_to_kg
)
from services.data_validation import (
    validate_activity_entry, validate_csv_content, validate_date_format, validate_activity_quantity
)
from services.scenario_engine import simulate_decarbonization_scenario
from services.forecasting import (
    run_forecasting_experiment, generate_synthetic_benchmark_dataset, 
    build_lagged_features, prepare_monthly_series, load_bdg2_benchmark_dataset
)
from services.anomaly_detector import detect_activity_anomalies
from services.report_generator import (
    generate_pdf_report, generate_csv_records_export, 
    generate_csv_monthly_summary, generate_csv_template
)

@pytest.fixture
def client():
    """Provides test client connected to an isolated temporary database."""
    app.config['TESTING'] = True
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    
    import models.database as db_module
    original_path_fn = db_module.get_db_path
    db_module.get_db_path = lambda: db_path
    
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client
        
    db_module.get_db_path = original_path_fn
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


# ============================================================
# 1. Calculation & Precision Tests
# ============================================================

class TestCalculationsAndPrecision:
    def test_known_electricity_benchmark(self):
        """Electricity: 1,000 kWh at 0.716 kg CO2e/kWh = 716.0 kg CO2e = 0.716 tonnes."""
        res = calculate_emission('electricity', 1000)
        assert res['co2e'] == 716.0
        assert res['co2e_tonnes'] == 0.716
        assert res['scope'] == 'Scope 2'

    def test_known_petrol_benchmark(self):
        """Petrol: 50 litres at 2.31 kg CO2e/L = 115.5 kg CO2e."""
        res = calculate_emission('petrol', 50)
        assert res['co2e'] == 115.5
        assert res['scope'] == 'Scope 1'

    def test_known_diesel_benchmark(self):
        """Diesel: 100 litres at 2.68 kg CO2e/L = 268.0 kg CO2e."""
        res = calculate_emission('diesel', 100)
        assert res['co2e'] == 268.0
        assert res['scope'] == 'Scope 1'

    def test_known_transit_bus_benchmark(self):
        """Bus: 200 km at 0.089 kg CO2e/km = 17.8 kg CO2e."""
        res = calculate_emission('transport_bus', 200)
        assert res['co2e'] == 17.8
        assert res['scope'] == 'Scope 3'

    def test_tonnes_conversions(self):
        assert kg_to_tonnes(2500.0) == 2.5
        assert kg_to_tonnes(0.0) == 0.0
        assert tonnes_to_kg(2.5) == 2500.0


# ============================================================
# 2. Input Rejection & Validation Safeguards
# ============================================================

class TestInputValidationSafeguards:
    def test_reject_zero_activity(self):
        with pytest.raises(ValueError, match="positive number"):
            calculate_emission('electricity', 0)

    def test_reject_negative_activity(self):
        with pytest.raises(ValueError, match="positive number"):
            calculate_emission('petrol', -15.5)

    def test_reject_nan_activity(self):
        with pytest.raises(ValueError, match="finite"):
            calculate_emission('electricity', float('nan'))

    def test_reject_inf_activity(self):
        with pytest.raises(ValueError, match="finite"):
            calculate_emission('electricity', float('inf'))

    def test_reject_none_category(self):
        with pytest.raises(ValueError):
            calculate_emission(None, 100)

    def test_reject_unknown_category(self):
        with pytest.raises(ValueError, match="Invalid category"):
            calculate_emission('unobtainium_fuel', 100)


# ============================================================
# 3. Unit Compatibility & Normalization
# ============================================================

class TestUnitCompatibility:
    def test_electricity_compatible_unit(self):
        compat, _ = validate_unit_compatibility('electricity', 'kWh')
        assert compat is True

    def test_electricity_incompatible_unit(self):
        compat, msg = validate_unit_compatibility('electricity', 'litres')
        assert compat is False
        assert "mismatch" in msg.lower()

    def test_unit_normalization_mwh_to_kwh(self):
        norm_val, norm_unit = normalize_unit_conversion('electricity', 2.0, 'MWh')
        assert norm_val == 2000.0
        assert norm_unit == 'kWh'

    def test_unit_normalization_miles_to_km(self):
        norm_val, norm_unit = normalize_unit_conversion('transport_bus', 10.0, 'miles')
        assert round(norm_val, 2) == 16.09
        assert norm_unit == 'km'

    def test_calculate_with_incompatible_unit_raises(self):
        with pytest.raises(ValueError, match="Unit mismatch"):
            calculate_emission('electricity', 100, unit='gallons')


# ============================================================
# 4. Factor Registry & Provenance
# ============================================================

class TestFactorRegistryProvenance:
    def test_registry_contains_cea_india_factor(self):
        registry = get_factor_registry()
        assert 'electricity' in registry
        elec = registry['electricity']
        assert 'CEA' in elec['source']
        assert 'India' in elec['region']
        assert elec['version'] is not None

    def test_registry_contains_ipcc_default_factors(self):
        registry = get_factor_registry()
        for fuel in ['petrol', 'diesel']:
            assert fuel in registry
            assert 'IPCC' in registry[fuel]['source']

    def test_registry_metadata_complete(self):
        registry = get_factor_registry()
        for k, v in registry.items():
            assert 'factor' in v
            assert 'factor_unit' in v
            assert 'unit' in v
            assert 'source' in v
            assert 'scope' in v


# ============================================================
# 5. CSV Parsing, Validation & Duplicate Warnings
# ============================================================

class TestCsvValidation:
    def test_valid_csv_parsing(self):
        csv_text = "date,category,activity,unit,data_source,notes\n2024-01,electricity,500,kWh,Utility Bill,Meter 1\n2024-01,petrol,40,litre,Fuel Receipt,Courier"
        valid, errors, warnings = validate_csv_content(csv_text)
        assert len(errors) == 0
        assert len(valid) == 2
        assert valid[0]['activity'] == 500.0

    def test_missing_mandatory_column(self):
        csv_text = "date,category\n2024-01,electricity"
        valid, errors, _ = validate_csv_content(csv_text)
        assert len(valid) == 0
        assert any("mandatory" in err for err in errors)

    def test_row_level_negative_error(self):
        csv_text = "date,category,activity\n2024-01,electricity,-50"
        valid, errors, _ = validate_csv_content(csv_text)
        assert len(valid) == 0
        assert any("Row 2" in err for err in errors)

    def test_in_batch_duplicate_warning(self):
        csv_text = "date,category,activity\n2024-01,electricity,500\n2024-01,electricity,500"
        valid, errors, warnings = validate_csv_content(csv_text)
        assert len(valid) == 2
        assert len(warnings) >= 1
        assert any("Duplicate" in w for w in warnings)


# ============================================================
# 6. Database Persistence of Scenarios & Experiments
# ============================================================

class TestDatabasePersistence:
    def test_scenario_crud(self, client):
        sc_id = insert_scenario(
            name='Solar Transition 2030',
            target_year=2030,
            elec_pct=50.0,
            fuel_pct=20.0,
            trans_pct=10.0,
            baseline_co2e=2000.0,
            scenario_co2e=1200.0,
            savings_co2e=800.0,
            gap_co2e=200.0,
            notes='Rooftop PV installation'
        )
        assert sc_id is not None
        all_sc = get_all_scenarios()
        assert any(s['name'] == 'Solar Transition 2030' for s in all_sc)

        delete_scenario(sc_id)
        assert all(s['id'] != sc_id for s in get_all_scenarios())

    def test_forecast_experiment_persistence(self, client):
        exp_id = insert_forecast_experiment({
            'dataset_type': 'Synthetic Benchmark',
            'data_points': 24,
            'train_points': 21,
            'test_points': 3,
            'split_cutoff': '2024-09',
            'model_name': 'Linear Regression',
            'features': 'lag_1, lag_2',
            'mae': 45.2,
            'rmse': 58.7,
            'r2': 0.82,
            'is_best': 1
        })
        assert exp_id is not None
        records = get_latest_forecast_experiments()
        assert len(records) >= 1
        assert records[0]['model_name'] == 'Linear Regression'

    def test_clear_all_emissions(self, client):
        from models.database import clear_all_emissions
        insert_emission_record('2024-01', 'electricity', 100, 'kWh', 0.716, 71.6)
        insert_emission_record('2024-02', 'petrol', 20, 'litre', 2.31, 46.2)
        assert len(get_all_emissions()) >= 2
        clear_all_emissions()
        assert len(get_all_emissions()) == 0


# ============================================================
# 7. Scenario Engine Calculations & Trajectory
# ============================================================

class TestScenarioEngine:
    def test_scenario_recalculation(self):
        base_dict = {'electricity': 1000.0, 'fuel': 400.0, 'transportation': 200.0, 'other': 0.0}
        sim = simulate_decarbonization_scenario(
            base_dict, target_reduction_pct=50, target_year=2035,
            elec_reduction_pct=30, fuel_reduction_pct=20, transport_reduction_pct=10
        )
        # 1000*(1-0.3) = 700; 400*(1-0.2) = 320; 200*(1-0.1) = 180 -> total = 1200
        assert sim['scenario_total_kg'] == 1200.0
        assert sim['savings_kg'] == 400.0
        # Target: 50% of 1600 = 800
        assert sim['target_emissions_kg'] == 800.0
        # Gap: 1200 - 800 = 400
        assert sim['remaining_gap_kg'] == 400.0
        assert sim['target_achieved'] is False
        assert len(sim['trajectory']) > 0

    def test_scenario_achieved_target(self):
        base_dict = {'electricity': 1000.0, 'fuel': 0.0, 'transportation': 0.0}
        sim = simulate_decarbonization_scenario(
            base_dict, target_reduction_pct=30, target_year=2030, elec_reduction_pct=50
        )
        # Reduced by 50%, target was 30% -> target achieved
        assert sim['target_achieved'] is True
        assert sim['remaining_gap_kg'] == 0.0

    def test_multiple_target_years_trajectory(self):
        base_dict = {'electricity': 1000.0, 'fuel': 500.0, 'transportation': 500.0, 'other': 0.0}
        current_year = 2026

        for t_year in [2030, 2035, 2040, 2050]:
            sim = simulate_decarbonization_scenario(base_dict, target_reduction_pct=50, target_year=t_year)
            traj = sim['trajectory']
            # Trajectory must terminate exactly at target_year
            assert traj[-1]['year'] == t_year
            # Trajectory must start at current year
            assert traj[0]['year'] == current_year
            # Number of points must equal years span + 1
            assert len(traj) == (t_year - current_year + 1)
            # Final allowance must equal 50% of baseline (1000 kg)
            assert traj[-1]['target_allowance_kg'] == 1000.0
            # Intermediate points must decrease monotonically
            for i in range(len(traj) - 1):
                assert traj[i]['target_allowance_kg'] >= traj[i+1]['target_allowance_kg']

    def test_multiple_reduction_percentages(self):
        base_dict = {'electricity': 2000.0, 'fuel': 0.0, 'transportation': 0.0, 'other': 0.0}
        total_baseline = 2000.0

        for pct in [10, 25, 50, 75, 100]:
            sim = simulate_decarbonization_scenario(base_dict, target_reduction_pct=pct, target_year=2030)
            expected_allowance = round(total_baseline * (1.0 - pct / 100.0), 2)
            assert sim['target_emissions_kg'] == expected_allowance
            expected_savings = round(total_baseline * (pct / 100.0), 2)
            assert sim['trajectory'][-1]['target_allowance_kg'] == expected_allowance


# ============================================================
# 8. Forecasting & Leakage Safeguards
# ============================================================

class TestForecastingAndLeakageSafeguards:
    def test_synthetic_benchmark_generator(self):
        data = generate_synthetic_benchmark_dataset(num_months=24)
        assert len(data) == 24 * 4 # 4 categories per month
        monthly = prepare_monthly_series(data)
        assert len(monthly) == 24
        # Verify strictly chronological
        for i in range(len(monthly) - 1):
            assert monthly[i]['month'] < monthly[i+1]['month']

    def test_lag_features_prevent_lookahead_leakage(self):
        data = generate_synthetic_benchmark_dataset(num_months=12)
        monthly = prepare_monthly_series(data)
        df = build_lagged_features(monthly)
        # Verify that for any row, lag_1 is strictly the previous month's observation
        for idx in range(len(df)):
            m_curr = df.iloc[idx]['month']
            m_orig_idx = [m['month'] for m in monthly].index(m_curr)
            assert df.iloc[idx]['lag_1'] == monthly[m_orig_idx - 1]['co2e']

    def test_experiment_runs_three_models_and_selects_best(self):
        data = generate_synthetic_benchmark_dataset(num_months=24)
        exp = run_forecasting_experiment(data, test_months=3)
        assert exp['has_sufficient_data'] is True
        assert len(exp['models']) == 3
        model_names = [m['model_name'] for m in exp['models']]
        assert 'Naive Baseline (Previous Month)' in model_names
        assert 'Linear Regression' in model_names
        assert 'Random Forest Regressor' in model_names
        
        # Verify error metrics are non-negative
        for m in exp['models']:
            assert m['mae'] >= 0
            assert m['rmse'] >= 0
            
        # Verify best model is declared
        assert any(m['is_best'] for m in exp['models'])
        assert exp['best_model'] is not None

    def test_bdg2_empirical_benchmark_loader(self):
        records = load_bdg2_benchmark_dataset()
        assert len(records) == 24
        # Verify valid positive values
        for r in records:
            assert r['activity'] > 150000.0 # ~200k kWh/mo
            assert r['co2e'] > 100000.0 # ~150 tonnes
            assert r['unit'] == 'kWh'
            assert 'Bear_education_Maryjane' in r['notes']

    def test_rolling_window_validation_produces_dynamic_future_projections(self):
        # Test on 24-month empirical BDG2 data
        records = load_bdg2_benchmark_dataset()
        exp = run_forecasting_experiment(records, dataset_type='BDG2 Benchmark')
        assert exp['has_sufficient_data'] is True
        assert len(exp['future_forecasts']) == 3
        # Ensure future forecasts are positive
        for f in exp['future_forecasts']:
            assert f['forecast_co2e'] > 0
        # If best model is Ridge/RF, ensure predictions vary dynamically
        f_vals = [f['forecast_co2e'] for f in exp['future_forecasts']]
        if exp['best_model'] in ['Linear Regression', 'Random Forest Regressor']:
            assert len(set(f_vals)) > 1, "Dynamic model should produce varying seasonal forecasts, not static flatline"


# ============================================================
# 9. Report Generation
# ============================================================

class TestReportGeneration:
    def test_pdf_generation_valid_stream(self):
        summary_data = {
            'records': [],
            'aggregation': {
                'total_kg': 1500.0,
                'total_tonnes': 1.5,
                'highest_category': 'Electricity',
                'highest_category_pct': 70.0,
                'categories': {'electricity': {'name': 'Grid Electricity', 'scope': 'Scope 2', 'kg_co2e': 1050.0, 'percentage': 70.0, 'count': 5, 'unit': 'kWh'}},
                'groups': {'electricity': 1050.0, 'fuel': 450.0, 'transportation': 0.0}
            },
            'target': {'baseline_emission': 2000.0, 'target_emission': 1000.0, 'target_reduction_percentage': 50, 'target_year': 2030},
            'recommendations': [{'priority': 'HIGH', 'source': 'Electricity', 'observed_evidence': '70% share', 'estimated_savings_kg': 150.0, 'estimated_savings_pct': 15, 'difficulty': 'Medium'}],
            'scenarios': [],
            'forecast': None
        }
        buf = generate_pdf_report(summary_data)
        pdf_bytes = buf.getvalue()
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b'%PDF')

    def test_csv_records_export(self):
        records = [
            {'id': 1, 'date': '2024-01', 'category': 'electricity', 'activity': 250.0, 'unit': 'kWh', 'emission_factor': 0.716, 'co2e': 179.0, 'data_source': 'Utility Bill', 'notes': 'Test'}
        ]
        csv_str = generate_csv_records_export(records)
        assert 'ID,Date,Category,Activity_Quantity' in csv_str
        assert '2024-01,electricity,250.0' in csv_str

    def test_csv_monthly_summary(self):
        series = [{'month': '2024-01', 'total_kg': 500.0, 'total_tonnes': 0.5, 'electricity_kg': 350.0, 'fuel_kg': 150.0, 'transportation_kg': 0.0, 'other_kg': 0.0}]
        csv_str = generate_csv_monthly_summary(series)
        assert 'Reporting_Month,Total_kg_CO2e' in csv_str
        assert '2024-01,500.0' in csv_str

    def test_csv_template(self):
        tmpl = generate_csv_template()
        assert 'date,category,activity,unit,data_source,notes' in tmpl


# ============================================================
# 10. HTTP Route Endpoints & Integration
# ============================================================

class TestHttpRouteIntegration:
    def test_activities_route(self, client):
        res = client.get('/activities')
        assert res.status_code == 200

    def test_emission_factors_route(self, client):
        res = client.get('/emission-factors')
        assert res.status_code == 200

    def test_forecasting_route(self, client):
        res = client.get('/forecasting')
        assert res.status_code == 200

    def test_forecasting_synthetic_route(self, client):
        res = client.get('/forecasting?benchmark=synthetic')
        assert res.status_code == 200

    def test_reports_page_route(self, client):
        res = client.get('/reports')
        assert res.status_code == 200

    def test_download_pdf_route(self, client):
        res = client.get('/reports/download-pdf')
        assert res.status_code == 200
        assert res.mimetype == 'application/pdf'

    def test_download_csv_route(self, client):
        res = client.get('/reports/download-csv')
        assert res.status_code == 200
        assert 'text/csv' in res.mimetype

    def test_download_monthly_csv_route(self, client):
        res = client.get('/reports/download-monthly-csv')
        assert res.status_code == 200
        assert 'text/csv' in res.mimetype

    def test_download_template_route(self, client):
        res = client.get('/download-template')
        assert res.status_code == 200
        assert 'text/csv' in res.mimetype

    def test_methodology_route(self, client):
        res = client.get('/methodology')
        assert res.status_code == 200

    def test_upload_csv_flow(self, client):
        csv_content = b"date,category,activity,unit,data_source,notes\n2024-03,electricity,400,kWh,Utility Bill,Upload Test\n"
        data = {'file': (io.BytesIO(csv_content), 'test_activities.csv')}
        res = client.post('/upload-csv', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert res.status_code == 200

    def test_api_simulate_scenario(self, client):
        payload = {
            'base_dict': {'electricity': 1000, 'fuel': 500, 'transportation': 200, 'other': 0},
            'target_pct': 50,
            'target_year': 2030,
            'elec_reduction': 25,
            'fuel_reduction': 20,
            'transport_reduction': 10
        }
        res = client.post('/api/simulate-scenario', json=payload)
        assert res.status_code == 200
        json_data = res.get_json()
        assert 'scenario_total_kg' in json_data
        assert 'savings_kg' in json_data

    def test_clear_all_data_route(self, client):
        insert_emission_record('2024-01', 'electricity', 100, 'kWh', 0.716, 71.6)
        res = client.post('/clear-all-data', follow_redirects=True)
        assert res.status_code == 200
        assert len(get_all_emissions()) == 0

    def test_api_inventory_summary(self, client):
        res = client.get('/api/inventory-summary')
        assert res.status_code == 200
        data = res.get_json()
        assert 'total_records' in data
        assert 'total_emissions_kg' in data
        assert 'scopes' in data
        assert 'audit_anomalies_flagged' in data

    def test_api_anomalies(self, client):
        res = client.get('/api/anomalies')
        assert res.status_code == 200
        data = res.get_json()
        assert 'total_inspected' in data
        assert 'anomalies_flagged' in data

    def test_forecasting_bdg2_route(self, client):
        res = client.get('/forecasting?benchmark=bdg2')
        assert res.status_code == 200
        assert b"Bear_education_Maryjane" in res.data


# ============================================================
# 11. AI Anomaly Detection Service Tests
# ============================================================

class TestAnomalyDetection:
    def test_insufficient_data_returns_safeguard(self):
        records = [{'activity': 100, 'category': 'electricity', 'co2e': 71.6}]
        res = detect_activity_anomalies(records)
        assert res['has_sufficient_data'] is False
        assert res['anomalies_flagged'] == 0

    def test_anomaly_detector_flags_uncharacteristic_spike(self):
        # 12 normal electricity observations around 3,000 kWh + 1 massive spike (25,000 kWh)
        records = []
        for i in range(12):
            records.append({
                'id': i + 1,
                'date': f'2023-{i+1:02d}',
                'category': 'electricity',
                'activity': 3000.0 + (i * 20),
                'unit': 'kWh',
                'co2e': round((3000.0 + i*20) * 0.716, 2)
            })
        # Injected anomaly spike
        records.append({
            'id': 99,
            'date': '2024-01',
            'category': 'electricity',
            'activity': 25000.0,
            'unit': 'kWh',
            'co2e': 25000.0 * 0.716
        })

        res = detect_activity_anomalies(records)
        assert res['has_sufficient_data'] is True
        assert res['anomalies_flagged'] >= 1
        flagged_ids = [a['record_id'] for a in res['flagged_records']]
        assert 99 in flagged_ids
        
        spike_item = next(a for a in res['flagged_records'] if a['record_id'] == 99)
        assert spike_item['audit_status'] == 'Requires Audit Investigation'
        assert 'Spike' in spike_item['flag_type']
        assert 'multi-month' in spike_item['recommended_action'].lower() or 'meter' in spike_item['recommended_action'].lower()

    def test_anomaly_detector_handles_missing_data_gracefully(self):
        records = [
            {'activity': None, 'category': 'electricity', 'co2e': None, 'notes': None},
            {'activity': 'invalid', 'category': 'petrol', 'co2e': 0.0},
        ] + [{'activity': 200, 'category': 'petrol', 'co2e': 462.0} for _ in range(8)]
        
        res = detect_activity_anomalies(records)
        assert isinstance(res, dict)
        assert 'anomalies_flagged' in res
