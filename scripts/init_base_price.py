#!/usr/bin/env python3
import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("API_TOKEN")
DOMAIN = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")


def shopify_get(session, url, **kwargs):
    """GET request with retry handling for Shopify rate limits."""
    while True:
        resp = session.get(url, **kwargs)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def graphql_post(session, query, variables=None):
    """POST to Shopify GraphQL API with retry on 429."""
    url = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"
    payload = {"query": query, "variables": variables or {}}
    while True:
        resp = session.post(url, json=payload)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def set_base_price(session, product_id, price):
    mutation = """
    mutation SetBase($mf: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $mf) {
        userErrors { field message }
      }
    }
    """
    variables = {
        "mf": [
            {
                "ownerId": f"gid://shopify/Product/{product_id}",
                "namespace": "custom",
                "key": "base_price",
                "type": "number_decimal",
                "value": str(price),
            }
        ]
    }
    resp = graphql_post(session, mutation, variables)
    if resp.ok:
        errors = resp.json()["data"]["metafieldsSet"]["userErrors"]
        if errors:
            for e in errors:
                print(f"❌ base_price {product_id}: {e['message']}")
        else:
            print(f"✅ {product_id} → {price}")
    else:
        print(f"❌ base_price {product_id}: {resp.text}")


def fetch_products(session):
    base_url = f"https://{DOMAIN}/admin/api/{API_VERSION}"
    products = []
    page_info = None
    while True:
        params = {"limit": 250, "fields": "id,variants"}
        if page_info:
            params["page_info"] = page_info
        resp = shopify_get(session, f"{base_url}/products.json", params=params)
        resp.raise_for_status()
        data = resp.json()
        products.extend(data["products"])
        link = resp.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        page_info = link.split("page_info=")[1].split(">")[0]
    return products


def main():
    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json",
    })
    print("🔄 Fetching products...")
    products = fetch_products(session)
    print(f"Found {len(products)} products")
    for prod in products:
        variants = prod.get("variants", [])
        if not variants:
            print(f"⚠️ No variants for product {prod['id']}")
            continue
        price = variants[0]["price"]
        set_base_price(session, prod["id"], price)
    print("🎉 Finished initializing base prices!")


if __name__ == "__main__":
    main()
