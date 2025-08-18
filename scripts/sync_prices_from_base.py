#!/usr/bin/env python3
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("API_TOKEN")
DOMAIN = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")


def shopify_get(session, url, **kwargs):
    while True:
        resp = session.get(url, timeout=30, **kwargs)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def graphql_post(session, query, variables=None):
    url = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"
    payload = {"query": query, "variables": variables or {}}
    while True:
        resp = session.post(url, json=payload, timeout=30)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def fetch_products(session):
    base_url = f"https://{DOMAIN}/admin/api/{API_VERSION}"
    page_info = None
    while True:
        params = {"limit": 250}
        if page_info:
            params["page_info"] = page_info
        resp = shopify_get(session, f"{base_url}/products.json", params=params)
        resp.raise_for_status()
        data = resp.json()
        for prod in data.get("products", []):
            yield prod
        link = resp.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        page_info = link.split("page_info=")[1].split(">")[0]


def get_base_price(session, product_id):
    base_url = f"https://{DOMAIN}/admin/api/{API_VERSION}"
    resp = shopify_get(session, f"{base_url}/products/{product_id}/metafields.json",
                        params={"namespace": "custom", "key": "base_price"})
    if resp.ok:
        for mf in resp.json().get("metafields", []):
            if mf.get("namespace") == "custom" and mf.get("key") == "base_price":
                return mf.get("value")
    return None


def set_prices(session, product_id, variant_ids, price):
    mutation = """
    mutation BulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
      productVariantsBulkUpdate(productId: $productId, variants: $variants) {
        userErrors { field message }
      }
    }
    """
    variants = [
        {
            "id": f"gid://shopify/ProductVariant/{vid}",
            "price": price,
            "compareAtPrice": price,
        }
        for vid in variant_ids
    ]
    for i in range(0, len(variants), 50):
        batch = variants[i:i+50]
        resp = graphql_post(
            session,
            mutation,
            {"productId": f"gid://shopify/Product/{product_id}", "variants": batch},
        )
        if resp.ok:
            errors = resp.json()["data"]["productVariantsBulkUpdate"]["userErrors"]
            if errors:
                for e in errors:
                    print(f"[ERROR] {e['field']}: {e['message']}")
        else:
            print(f"[ERROR] {resp.text}")


def main():
    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json",
    })
    for prod in fetch_products(session):
        base_price = get_base_price(session, prod["id"])
        if base_price is None:
            continue
        vids = [v["id"] for v in prod.get("variants", [])]
        set_prices(session, prod["id"], vids, str(base_price))
        print(f"[OK] {prod['id']} -> {base_price}")
    print("[DONE] Synced prices from base_price")


if __name__ == "__main__":
    main()
