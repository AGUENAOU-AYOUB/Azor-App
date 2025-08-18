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


def login(client):
    return client.post('/login', data={'username': 'admin', 'password': 'password'})


def test_ensemble_requires_login(client):
    resp = client.get('/ensemble')
    assert resp.status_code == 302


def test_ensemble_after_login(client):
    login(client)
    resp = client.get('/ensemble')
    assert resp.status_code == 200
    assert b'Ensemble' in resp.data
