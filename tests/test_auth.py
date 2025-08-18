import os
import pytest
from webapp import create_app

@pytest.fixture
def app():
    os.environ['SECRET_KEY'] = 'test-key'
    os.environ['ADMIN_USERNAME'] = 'admin'
    os.environ['ADMIN_PASSWORD'] = 'password'
    os.environ['WTF_CSRF_ENABLED'] = 'false'
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_home_requires_login(client):
    resp = client.get('/')
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_login_with_default_credentials(client):
    resp = client.post('/login', data={'username': 'admin', 'password': 'password'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Welcome' in resp.data


def test_login_form_contains_csrf(client):
    resp = client.get('/login')
    assert resp.status_code == 200
    assert b'<input type="hidden" name="csrf_token"' in resp.data
