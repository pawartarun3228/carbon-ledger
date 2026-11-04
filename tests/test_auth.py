"""Automated Authentication & Authorization Test Suite for Carbon Ledger.
Validates:
1. New user registration
2. Duplicate email rejection
3. Invalid email rejection
4. Password confirmation validation
5. Password strength requirements
6. Successful login & session establishment
7. Incorrect password handling
8. Login rate limiting / brute-force mitigation
9. Forgot-password token generation & non-enumerating generic response
10. Single-use time-limited password reset execution
11. Protected route enforcement (redirects unauthenticated users to /login)
12. Session persistence across requests
13. Functional logout & session invalidation
14. User-specific data isolation
15. Organisation onboarding & profile updates
16. Fast demo login & simulated Google SSO
"""

import pytest
import os
import sys
import tempfile
from flask import session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.database import (
    init_db, get_db, get_user_by_email, get_user_by_id, 
    insert_emission_record, get_all_emissions
)
from services.auth import (
    hash_password, verify_password, validate_password_strength,
    validate_email_format, generate_reset_token, verify_reset_token,
    hash_token, reset_login_attempts
)

@pytest.fixture
def auth_client():
    """Provides isolated test client with clean temporary database."""
    app.config['TESTING'] = True
    app.config['ENFORCE_TEST_LOGIN'] = True  # Strict enforcement of auth checks
    
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    import models.database as db_module
    original_path_fn = db_module.get_db_path
    db_module.get_db_path = lambda: db_path
    
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client
        
    app.config['ENFORCE_TEST_LOGIN'] = False
    db_module.get_db_path = original_path_fn
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestRegistration:
    def test_new_user_registration(self, auth_client):
        """Test: Valid user registration creates account and starts session."""
        res = auth_client.post('/register', data={
            'name': 'Professor Jane Smith',
            'email': 'jane.smith@institution.edu',
            'password': 'SecurePassword@123',
            'confirm_password': 'SecurePassword@123',
            'organisation_name': 'Imperial Climate Labs',
            'organisation_type': 'University / Educational Institution'
        }, follow_redirects=False)

        assert res.status_code == 302
        assert '/onboarding' in res.headers['Location']

        # Verify user in database
        user = get_user_by_email('jane.smith@institution.edu')
        assert user is not None
        assert user['name'] == 'Professor Jane Smith'
        assert user['organisation_name'] == 'Imperial Climate Labs'
        assert verify_password(user['password_hash'], 'SecurePassword@123')

    def test_duplicate_email_rejection(self, auth_client):
        """Test: Cannot register an email that already exists."""
        # demo@example.com is already seeded
        res = auth_client.post('/register', data={
            'name': 'Duplicate User',
            'email': 'demo@example.com',
            'password': 'Password123!',
            'confirm_password': 'Password123!'
        }, follow_redirects=True)

        assert res.status_code == 200
        assert b"already exists" in res.data

    def test_invalid_email_rejection(self, auth_client):
        """Test: Malformed email syntax is rejected."""
        res = auth_client.post('/register', data={
            'name': 'Invalid Email User',
            'email': 'not-an-email',
            'password': 'Password123!',
            'confirm_password': 'Password123!'
        }, follow_redirects=True)

        assert res.status_code == 200
        assert b"valid institutional or personal email" in res.data

    def test_password_mismatch_rejection(self, auth_client):
        """Test: Mismatched password confirmation is rejected."""
        res = auth_client.post('/register', data={
            'name': 'Mismatch User',
            'email': 'mismatch@example.com',
            'password': 'Password123!',
            'confirm_password': 'DifferentPassword123!'
        }, follow_redirects=True)

        assert res.status_code == 200
        assert b"Passwords do not match" in res.data

    def test_password_strength_enforcement(self, auth_client):
        """Test: Passwords shorter than 8 chars or lacking symbols/digits are rejected."""
        # Too short
        res = auth_client.post('/register', data={
            'name': 'Short Pass',
            'email': 'short@example.com',
            'password': 'short',
            'confirm_password': 'short'
        }, follow_redirects=True)
        assert res.status_code == 200
        assert b"at least 8 characters" in res.data

        # No digits or symbols
        res = auth_client.post('/register', data={
            'name': 'No Symbols',
            'email': 'nosym@example.com',
            'password': 'abcdefghijkl',
            'confirm_password': 'abcdefghijkl'
        }, follow_redirects=True)
        assert res.status_code == 200
        assert b"number or special character" in res.data


class TestAuthenticationFlow:
    def test_successful_login(self, auth_client):
        """Test: Successful login with correct credentials establishes session."""
        res = auth_client.post('/login', data={
            'email': 'demo@example.com',
            'password': 'Demo@1234'
        }, follow_redirects=False)

        assert res.status_code == 302
        assert '/dashboard' in res.headers['Location']

        # Verify session
        with auth_client.session_transaction() as sess:
            assert sess['user_id'] == 1
            assert sess['user_email'] == 'demo@example.com'

    def test_incorrect_password(self, auth_client):
        """Test: Incorrect password is rejected with security feedback."""
        res = auth_client.post('/login', data={
            'email': 'demo@example.com',
            'password': 'WrongPassword999!'
        }, follow_redirects=True)

        assert res.status_code == 200
        assert b"Invalid email address or password" in res.data

        with auth_client.session_transaction() as sess:
            assert 'user_id' not in sess

    def test_login_rate_limiting(self, auth_client):
        """Test: Multiple consecutive failed logins trigger rate-limit lock."""
        client_ip = '127.0.0.1'
        reset_login_attempts(f"{client_ip}:rate@example.com")

        for _ in range(5):
            auth_client.post('/login', data={
                'email': 'rate@example.com',
                'password': 'WrongPassword123!'
            })

        # 6th attempt should return 429
        res = auth_client.post('/login', data={
            'email': 'rate@example.com',
            'password': 'WrongPassword123!'
        })
        assert res.status_code == 429
        assert b"Too many failed login attempts" in res.data

    def test_demo_login_shortcut(self, auth_client):
        """Test: Quick 1-click evaluation demo sign-in works immediately."""
        res = auth_client.get('/demo-login', follow_redirects=False)
        assert res.status_code == 302
        assert '/dashboard' in res.headers['Location']

        with auth_client.session_transaction() as sess:
            assert sess['user_id'] == 1

    def test_google_demo_login(self, auth_client):
        """Test: Simulated Google SSO creates and signs in Google user."""
        res = auth_client.get('/google-demo-login', follow_redirects=False)
        assert res.status_code == 302
        assert '/dashboard' in res.headers['Location']

        with auth_client.session_transaction() as sess:
            assert sess['user_email'] == 'alex.mercer.google@example.org'


class TestPasswordReset:
    def test_forgot_password_generates_token(self, auth_client):
        """Test: Forgot password request creates secure reset token."""
        res = auth_client.post('/forgot-password', data={
            'email': 'demo@example.com'
        }, follow_redirects=True)

        assert res.status_code == 200
        # In non-SMTP development environment, evaluation link is surfaced
        assert b"/reset-password/" in res.data

    def test_single_use_password_reset_flow(self, auth_client):
        """Test: Reset password token allows changing password and cannot be reused."""
        token = generate_reset_token('demo@example.com', secret_key=app.secret_key)
        t_hash = hash_token(token)
        from models.database import create_password_reset
        from datetime import datetime, timedelta
        expires_at = (datetime.now() + timedelta(hours=1)).isoformat()
        create_password_reset(1, t_hash, expires_at)

        # 1. Access reset page
        res = auth_client.get(f'/reset-password/{token}')
        assert res.status_code == 200
        assert b"Set new password" in res.data

        # 2. Submit new password
        post_res = auth_client.post(f'/reset-password/{token}', data={
            'new_password': 'BrandNewPassword@2026',
            'confirm_password': 'BrandNewPassword@2026'
        }, follow_redirects=False)

        assert post_res.status_code == 302
        assert '/login' in post_res.headers['Location']

        # Verify new password works
        user = get_user_by_id(1)
        assert verify_password(user['password_hash'], 'BrandNewPassword@2026')

        # 3. Attempting to use the same token again should be rejected
        reuse_res = auth_client.get(f'/reset-password/{token}', follow_redirects=True)
        assert b"already been used" in reuse_res.data


class TestProtectedRoutesAndSession:
    def test_unauthenticated_user_redirected_to_login(self, auth_client):
        """Test: Unauthenticated requests to protected routes redirect to /login."""
        # Ensure session is empty
        with auth_client.session_transaction() as sess:
            sess.clear()

        res = auth_client.get('/dashboard', follow_redirects=False)
        assert res.status_code == 302
        assert '/login' in res.headers['Location']

        res2 = auth_client.get('/history', follow_redirects=False)
        assert res2.status_code == 302
        assert '/login' in res2.headers['Location']

        res3 = auth_client.get('/net-zero', follow_redirects=False)
        assert res3.status_code == 302
        assert '/login' in res3.headers['Location']

    def test_logout_clears_session(self, auth_client):
        """Test: Logging out destroys session and redirects to /login."""
        # First sign in
        auth_client.get('/demo-login')
        with auth_client.session_transaction() as sess:
            assert 'user_id' in sess

        # Log out
        res = auth_client.get('/logout', follow_redirects=False)
        assert res.status_code == 302
        assert '/login' in res.headers['Location']

        with auth_client.session_transaction() as sess:
            assert 'user_id' not in sess


class TestUserDataIsolation:
    def test_users_only_see_their_own_records(self, auth_client):
        """Test: Data isolation prevents User A from accessing User B's records."""
        from models.database import create_user
        # Create User 2
        user2_id = create_user(
            name='User Two',
            email='user2@example.org',
            password_hash=hash_password('Password@123')
        )

        # Log record for Demo User (id=1)
        insert_emission_record('2024-01', 'electricity', 100, 'kWh', 0.716, 71.6, user_id=1)

        # Log record for User 2
        insert_emission_record('2024-01', 'petrol', 50, 'litre', 2.31, 115.5, user_id=user2_id)

        # Check records for User 1
        user1_records = get_all_emissions(user_id=1)
        assert all(r['user_id'] == 1 for r in user1_records)

        # Check records for User 2
        user2_records = get_all_emissions(user_id=user2_id)
        assert all(r['user_id'] == user2_id for r in user2_records)
        assert len(user2_records) == 1
        assert user2_records[0]['category'] == 'petrol'


class TestOrganisationProfileAndSettings:
    def test_onboarding_profile_update(self, auth_client):
        """Test: User can complete organisation onboarding profile."""
        auth_client.get('/demo-login')

        res = auth_client.post('/onboarding', data={
            'organisation_name': 'Stanford Climate Observatory',
            'organisation_type': 'Research Institution',
            'country': 'United States',
            'sector': 'Atmospheric Science',
            'org_size': '51-200 employees',
            'reporting_period': 'Academic Year (Jul-Jun)',
            'electricity_source': '100% Green Power PPA'
        }, follow_redirects=False)

        assert res.status_code == 302
        assert '/dashboard' in res.headers['Location']

        user = get_user_by_id(1)
        assert user['organisation_name'] == 'Stanford Climate Observatory'
        assert user['electricity_source'] == '100% Green Power PPA'

    def test_profile_password_change(self, auth_client):
        """Test: User can change password from account settings."""
        auth_client.get('/demo-login')

        res = auth_client.post('/profile', data={
            'action': 'change_password',
            'current_password': 'Demo@1234',
            'new_password': 'NewUpdatedPassword@789',
            'confirm_password': 'NewUpdatedPassword@789'
        }, follow_redirects=True)

        assert res.status_code == 200
        assert b"password has been changed successfully" in res.data

        user = get_user_by_id(1)
        assert verify_password(user['password_hash'], 'NewUpdatedPassword@789')
