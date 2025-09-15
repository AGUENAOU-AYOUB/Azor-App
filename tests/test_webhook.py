import os
import json
import hmac
import hashlib
import base64
import pytest

from webapp import create_app
from webapp import webhook as webhook_mod


def _sign(body: bytes) -> str:
    secret = os.environ['SHOPIFY_WEBHOOK_SECRET'].encode()
    digest = hmac.new(secret, body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


@pytest.fixture
def app():
    os.environ['SECRET_KEY'] = 'test'
    os.environ['WTF_CSRF_ENABLED'] = 'false'
    os.environ['SHOPIFY_WEBHOOK_SECRET'] = 'shhh'
    os.environ['API_TOKEN'] = 'token'
    os.environ['SHOP_DOMAIN'] = 'example.myshopify.com'
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_webhook_triggers_update(monkeypatch, client):
    called = {}

    def fake_update(pid, price):
        called['pid'] = pid
        called['price'] = price

    monkeypatch.setattr(webhook_mod, '_update_variant_prices', fake_update)

    payload = {
        'namespace': 'custom',
        'key': 'base_price',
        'owner_id': 42,
        'value': '19.99',
    }
    body = json.dumps(payload).encode()
    hmac_header = _sign(body)
    resp = client.post(
        '/webhook/metafield',
        data=body,
        headers={'Content-Type': 'application/json', 'X-Shopify-Hmac-SHA256': hmac_header},
    )
    assert resp.status_code == 200
    assert called == {'pid': 42, 'price': '19.99'}


def test_metaobject_webhook_triggers_update(monkeypatch, client):
    called = {}

    def fake_update(pid, price):
        called['pid'] = pid
        called['price'] = price

    monkeypatch.setattr(webhook_mod, '_update_variant_prices', fake_update)

    payload = {
        'data': {
            'product': {'id': 7},
            'price': '29.99',
        }
    }
    body = json.dumps(payload).encode()
    hmac_header = _sign(body)
    resp = client.post(
        '/webhook/metaobject',
        data=body,
        headers={'Content-Type': 'application/json', 'X-Shopify-Hmac-SHA256': hmac_header},
    )
    assert resp.status_code == 200
    assert called == {'pid': 7, 'price': '29.99'}


def test_webhook_invalid_hmac(client):
    payload = {'namespace': 'custom', 'key': 'base_price', 'owner_id': 1, 'value': '9'}
    body = json.dumps(payload).encode()
    resp = client.post(
        '/webhook/metafield',
        data=body,
        headers={'Content-Type': 'application/json', 'X-Shopify-Hmac-SHA256': 'bad'},
    )
    assert resp.status_code == 401
