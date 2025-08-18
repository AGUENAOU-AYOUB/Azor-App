import os
import sys
import pytest
from webapp import create_app
from webapp import routes as routes_mod


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


def setup_patches(monkeypatch):
    captured = {}

    def fake_enqueue(cmd):
        captured['cmd'] = cmd
        return 'job'

    def fake_stream(job_id):
        if False:
            yield None

    monkeypatch.setattr(routes_mod, 'enqueue', fake_enqueue)
    monkeypatch.setattr(routes_mod, 'stream', fake_stream)
    return captured


def test_stream_percentage_uses_sys_executable(client, monkeypatch):
    captured = setup_patches(monkeypatch)
    login(client)
    resp = client.get('/stream/percentage?percent=5')
    assert resp.status_code == 200
    assert captured['cmd'][0] == sys.executable
    assert captured['cmd'][1] == routes_mod.SCRIPTS['percentage']
    assert captured['cmd'][2:] == ['--percent', '5']


def test_stream_variant_uses_sys_executable(client, monkeypatch):
    captured = setup_patches(monkeypatch)
    login(client)
    resp = client.get('/stream/variant')
    assert resp.status_code == 200
    assert captured['cmd'] == [sys.executable, routes_mod.SCRIPTS['variant']]


def test_stream_reset_uses_sys_executable(client, monkeypatch):
    captured = setup_patches(monkeypatch)
    login(client)
    resp = client.get('/stream/reset')
    assert resp.status_code == 200
    assert captured['cmd'] == [sys.executable, routes_mod.SCRIPTS['reset']]


def test_stream_baseprice_uses_sys_executable(client, monkeypatch):
    captured = setup_patches(monkeypatch)
    login(client)
    resp = client.get('/stream/baseprice')
    assert resp.status_code == 200
    assert captured['cmd'] == [sys.executable, routes_mod.SCRIPTS['baseprice']]


def test_stream_ensemble_uses_sys_executable(client, monkeypatch):
    captured = setup_patches(monkeypatch)
    login(client)
    resp = client.get('/stream/ensemble')
    assert resp.status_code == 200
    assert captured['cmd'] == [sys.executable, routes_mod.SCRIPTS['ensemble']]
