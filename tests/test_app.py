import pytest
import os
import sys
import json
import tempfile
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.database import init_db, get_db, get_db_path
from services.emission_calculator import calculate_emission, load_emission_factors, get_available_categories
from services.recommendation_engine import generate_recommendations
from services.net_zero import calculate_net_zero_plan, generate_roadmap_phases
from services.prediction import predict_next_month


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def client():
    """Create a test client with a temporary database."""
    app.config['TESTING'] = True
    
    # Use a temporary database for tests
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    
    # Monkey-patch get_db_path to use temp db
    import models.database as db_module
    original_path_fn = db_module.get_db_path
    db_module.get_db_path = lambda: db_path
    
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client
    
    # Restore and cleanup
    db_module.get_db_path = original_path_fn
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def emission_factors():
    """Load emission factors."""
    return load_emission_factors()


# ============================================================
# 1. Emission Calculation Tests
# ============================================================

class TestEmissionCalculation:
    """Test the emission calculation engine."""
    
    def test_electricity_calculation(self):
        """Test: CO2e = kWh × emission factor for electricity."""
        result = calculate_emission('electricity', 250)
        factors = load_emission_factors()
        expected = 250 * factors['electricity']['factor']
        assert result['co2e'] == round(expected, 4)
        assert result['category'] == 'electricity'
        assert result['unit'] == 'kWh'
    
    def test_petrol_calculation(self):
        """Test: CO2e = litres × emission factor for petrol."""
        result = calculate_emission('petrol', 40)
        factors = load_emission_factors()
        expected = 40 * factors['petrol']['factor']
        assert result['co2e'] == round(expected, 4)
        assert result['category'] == 'petrol'
        assert result['unit'] == 'litre'
    
    def test_diesel_calculation(self):
        """Test: CO2e = litres × emission factor for diesel."""
        result = calculate_emission('diesel', 30)
        factors = load_emission_factors()
        expected = 30 * factors['diesel']['factor']
        assert result['co2e'] == round(expected, 4)
    
    def test_transport_car_calculation(self):
        """Test: CO2e = km × emission factor for car transport."""
        result = calculate_emission('transport_car_petrol', 100)
        factors = load_emission_factors()
        expected = 100 * factors['transport_car_petrol']['factor']
        assert result['co2e'] == round(expected, 4)
    
    def test_zero_activity_raises_error(self):
        """Test: Zero activity value should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_emission('electricity', 0)
    
    def test_negative_activity_raises_error(self):
        """Test: Negative activity value should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_emission('electricity', -100)
    
    def test_invalid_category_raises_error(self):
        """Test: Invalid category should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_emission('nuclear_reactor', 500)
    
    def test_calculation_formula(self):
        """Test: Verify CO2e = Activity × Emission Factor."""
        result = calculate_emission('electricity', 100)
        assert result['co2e'] == round(result['activity'] * result['emission_factor'], 4)
    
    def test_available_categories(self):
        """Test: Should return a non-empty list of categories."""
        categories = get_available_categories()
        assert len(categories) > 0
        assert all('key' in c and 'name' in c and 'unit' in c for c in categories)


# ============================================================
# 2. Database Tests
# ============================================================

class TestDatabase:
    """Test database operations."""
    
    def test_database_creation(self, client):
        """Test: Database and tables should be created."""
        from models.database import get_db
        conn = get_db()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row['name'] for row in cursor.fetchall()]
        conn.close()
        assert 'users' in tables
        assert 'emission_records' in tables
        assert 'net_zero_targets' in tables
    
    def test_insert_emission_record(self, client):
        """Test: Should insert an emission record."""
        from models.database import insert_emission_record, get_all_emissions
        record_id = insert_emission_record(
            date='2024-01',
            category='electricity',
            activity=250,
            unit='kWh',
            emission_factor=0.716,
            co2e=179.0
        )
        assert record_id is not None
        records = get_all_emissions()
        assert len(records) >= 1
    
    def test_delete_emission_record(self, client):
        """Test: Should delete an emission record."""
        from models.database import insert_emission_record, delete_emission, get_all_emissions
        record_id = insert_emission_record(
            date='2024-01', category='electricity',
            activity=250, unit='kWh',
            emission_factor=0.716, co2e=179.0
        )
        delete_emission(record_id)
        records = get_all_emissions()
        assert all(r['id'] != record_id for r in records)
    
    def test_filter_by_category(self, client):
        """Test: Should filter records by category."""
        from models.database import insert_emission_record, get_all_emissions
        insert_emission_record('2024-01', 'electricity', 250, 'kWh', 0.716, 179.0)
        insert_emission_record('2024-01', 'petrol', 40, 'litre', 2.31, 92.4)
        
        elec_records = get_all_emissions(category='electricity')
        assert all(r['category'] == 'electricity' for r in elec_records)
    
    def test_default_user_created(self, client):
        """Test: Default demo user should exist."""
        from models.database import get_db
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE id = 1').fetchone()
        conn.close()
        assert user is not None
        assert user['name'] == 'Demo User'


# ============================================================
# 3. Recommendation Engine Tests
# ============================================================

class TestRecommendations:
    """Test the recommendation engine."""
    
    def test_empty_data_returns_empty(self):
        """Test: No data should return no recommendations."""
        result = generate_recommendations([])
        assert result == []
    
    def test_electricity_dominant_recommendations(self):
        """Test: Should recommend electricity reduction when it's dominant."""
        records = [
            {'category': 'electricity', 'co2e': 200},
            {'category': 'petrol', 'co2e': 50},
        ]
        result = generate_recommendations(records)
        assert len(result) > 0
        # Electricity should be first (highest)
        assert result[0]['category_group'] == 'electricity'
        assert result[0]['priority'] in ('HIGH', 'CRITICAL')
    
    def test_transport_dominant_recommendations(self):
        """Test: Should recommend transport reduction when it's dominant."""
        records = [
            {'category': 'electricity', 'co2e': 30},
            {'category': 'transport_car_petrol', 'co2e': 200},
        ]
        result = generate_recommendations(records)
        assert len(result) > 0
        assert result[0]['category_group'] == 'transportation'
    
    def test_recommendations_have_tips(self):
        """Test: Each recommendation should have actionable tips."""
        records = [
            {'category': 'electricity', 'co2e': 100},
            {'category': 'petrol', 'co2e': 80},
        ]
        result = generate_recommendations(records)
        for rec in result:
            assert 'tips' in rec
            assert len(rec['tips']) > 0
    
    def test_impact_classification(self):
        """Test: Impact levels should correspond to percentage thresholds."""
        from services.recommendation_engine import _classify_impact
        assert _classify_impact(10) == ('Low Impact', 'LOW')
        assert _classify_impact(30) == ('Moderate Impact', 'MEDIUM')
        assert _classify_impact(50) == ('High Impact', 'HIGH')
        assert _classify_impact(70) == ('Very High Impact', 'CRITICAL')


# ============================================================
# 4. Net-Zero Calculation Tests
# ============================================================

class TestNetZero:
    """Test net-zero planning calculations."""
    
    def test_basic_calculation(self):
        """Test: Basic net-zero target calculation."""
        plan = calculate_net_zero_plan(
            baseline_emission=1200,
            target_reduction_pct=30,
            target_year=2030
        )
        assert plan['baseline'] == 1200
        assert plan['target_emission'] == 840
        assert plan['required_reduction'] == 360
        assert plan['target_year'] == 2030
    
    def test_full_reduction(self):
        """Test: 100% reduction should target 0."""
        plan = calculate_net_zero_plan(
            baseline_emission=1000,
            target_reduction_pct=100,
            target_year=2035
        )
        assert plan['target_emission'] == 0
        assert plan['required_reduction'] == 1000
    
    def test_progress_calculation(self):
        """Test: Progress should be calculated when current emission provided."""
        plan = calculate_net_zero_plan(
            baseline_emission=1200,
            target_reduction_pct=50,
            target_year=2030,
            current_annual_emission=900
        )
        # Reduced from 1200 to 900 = 300 reduction
        # Required: 600 reduction
        # Progress: 300/600 * 100 = 50%
        assert plan['progress_pct'] == 50.0
    
    def test_invalid_baseline_raises_error(self):
        """Test: Zero or negative baseline should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_net_zero_plan(0, 30, 2030)
    
    def test_invalid_reduction_raises_error(self):
        """Test: Reduction > 100 should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_net_zero_plan(1200, 150, 2030)
    
    def test_roadmap_has_phases(self):
        """Test: Roadmap should generate phases."""
        phases = generate_roadmap_phases(1200, 840, 2030)
        assert len(phases) == 5
        assert all('title' in p and 'actions' in p for p in phases)


# ============================================================
# 5. Prediction Tests
# ============================================================

class TestPrediction:
    """Test the prediction module."""
    
    def test_insufficient_data(self):
        """Test: Should report insufficient data with < 4 months."""
        records = [
            {'date': '2024-01', 'co2e': 100},
            {'date': '2024-02', 'co2e': 110},
        ]
        result = predict_next_month(records)
        assert result['has_sufficient_data'] is False
        assert 'more' in result['message'].lower() or 'insufficient' in result['message'].lower() or 'at least' in result['message'].lower()
    
    def test_sufficient_data_gives_prediction(self):
        """Test: Should produce a prediction with >= 4 months."""
        records = [
            {'date': '2024-01', 'co2e': 100},
            {'date': '2024-02', 'co2e': 110},
            {'date': '2024-03', 'co2e': 120},
            {'date': '2024-04', 'co2e': 130},
            {'date': '2024-05', 'co2e': 140},
        ]
        result = predict_next_month(records)
        assert result['has_sufficient_data'] is True
        assert result['predicted_value'] is not None
        assert result['predicted_value'] > 0
    
    def test_prediction_has_r_squared(self):
        """Test: Prediction should include R² score."""
        records = [
            {'date': '2024-01', 'co2e': 100},
            {'date': '2024-02', 'co2e': 120},
            {'date': '2024-03', 'co2e': 115},
            {'date': '2024-04', 'co2e': 130},
        ]
        result = predict_next_month(records)
        if result['has_sufficient_data']:
            assert result['r_squared'] is not None
    
    def test_empty_data(self):
        """Test: Empty data should return insufficient."""
        result = predict_next_month([])
        assert result['has_sufficient_data'] is False


# ============================================================
# 6. Flask Route Tests
# ============================================================

class TestRoutes:
    """Test Flask routes return correct status codes."""
    
    def test_home_page(self, client):
        """Test: Home page should load."""
        response = client.get('/')
        assert response.status_code == 200
    
    def test_dashboard_page(self, client):
        """Test: Dashboard should load."""
        response = client.get('/dashboard')
        assert response.status_code == 200
    
    def test_add_data_page(self, client):
        """Test: Add data page should load."""
        response = client.get('/add-data')
        assert response.status_code == 200
    
    def test_history_page(self, client):
        """Test: History page should load."""
        response = client.get('/history')
        assert response.status_code == 200
    
    def test_recommendations_page(self, client):
        """Test: Recommendations page should load."""
        response = client.get('/recommendations')
        assert response.status_code == 200
    
    def test_net_zero_page(self, client):
        """Test: Net-zero page should load."""
        response = client.get('/net-zero')
        assert response.status_code == 200
    
    def test_prediction_page(self, client):
        """Test: Prediction page should load."""
        response = client.get('/prediction')
        assert response.status_code == 200
    
    def test_add_data_post(self, client):
        """Test: POST to add-data should save and redirect."""
        response = client.post('/add-data', data={
            'date': '2024-01',
            'category': 'electricity',
            'activity': '250'
        }, follow_redirects=True)
        assert response.status_code == 200
    
    def test_add_data_invalid(self, client):
        """Test: Invalid data should show error."""
        response = client.post('/add-data', data={
            'date': '2024-01',
            'category': 'electricity',
            'activity': '-50'
        }, follow_redirects=True)
        assert response.status_code == 200
    
    def test_api_emissions(self, client):
        """Test: API should return JSON."""
        response = client.get('/api/emissions')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'records' in data
    
    def test_api_monthly_emissions(self, client):
        """Test: Monthly API should return labels and data."""
        response = client.get('/api/monthly-emissions')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'labels' in data
        assert 'data' in data
    
    def test_api_category_emissions(self, client):
        """Test: Category API should return labels and data."""
        response = client.get('/api/category-emissions')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'labels' in data
        assert 'data' in data
    
    def test_load_demo_data(self, client):
        """Test: Loading demo data should redirect."""
        response = client.post('/api/load-demo-data', follow_redirects=True)
        assert response.status_code == 200
    
    def test_clear_demo_data(self, client):
        """Test: Clearing demo data should redirect."""
        response = client.post('/api/clear-demo-data', follow_redirects=True)
        assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
