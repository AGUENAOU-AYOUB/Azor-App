import importlib
import pytest


class DummyResp:
    def __init__(self, data, link):
        self._data = data
        self.status_code = 200
        self.headers = {'Link': link}
        self.ok = True

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


@pytest.fixture
def init_module(monkeypatch):
    monkeypatch.setenv('API_TOKEN', 'token')
    monkeypatch.setenv('SHOP_DOMAIN', 'example.com')
    monkeypatch.setenv('API_VERSION', '2024-04')
    module = importlib.reload(importlib.import_module('scripts.init_base_price'))
    return module


def test_processed_matches_unique_products(init_module, monkeypatch, capsys):
    responses = [
        DummyResp({'products': [{'id': 1, 'variants': [{'price': 1}]}]},
                  '<https://example.com/admin/api/2024-04/products.json?page_info=page2&limit=250>; rel="next"'),
        DummyResp({'products': [{'id': 2, 'variants': [{'price': 2}]}]},
                  '<https://example.com/admin/api/2024-04/products.json?page_info=page1&limit=250>; rel="previous", <https://example.com/admin/api/2024-04/products.json?page_info=page3&limit=250>; rel="next"'),
        DummyResp({'products': [{'id': 3, 'variants': [{'price': 3}]}]},
                  '<https://example.com/admin/api/2024-04/products.json?page_info=page2&limit=250>; rel="previous"'),
    ]

    def fake_shopify_get(session, url, params=None, **kwargs):
        return responses.pop(0)

    processed_ids = []

    def fake_set_base_prices(session, products, progress_cb):
        processed_ids.extend(pid for pid, _ in products)
        progress_cb(len(products))

    monkeypatch.setattr(init_module, 'shopify_get', fake_shopify_get)
    monkeypatch.setattr(init_module, 'set_base_prices', fake_set_base_prices)

    init_module.main()

    captured = capsys.readouterr()
    assert '[DONE] Finished initializing base prices!' in captured.out
    assert '[PROGRESS] processed 3' in captured.out
    assert processed_ids == [1, 2, 3]
    assert len(set(processed_ids)) == 3
