#!/usr/bin/env python3
import os

import time
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN       = os.getenv("API_TOKEN")
DOMAIN      = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")


def shopify_get(session, url, **kwargs):

    while True:
        resp = session.get(url, **kwargs)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def graphql_post(session, query, variables=None):

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

        errs = resp.json()["data"]["metafieldsSet"]["userErrors"]
        if errs:
            for e in errs:
                print(f"❌ {product_id}: {e['message']}")
        else:
            print(f"✅ {product_id} → {price}")
    else:
        print(f"❌ {product_id}: {resp.text}")


def main():
    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json",
    })

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
            price = prod["variants"][0]["price"]
            set_base_price(session, prod["id"], price)

        link = resp.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        page_info = link.split("page_info=")[1].split(">")[0]

    print("🎉 Finished initializing base prices!")


if __name__ == "__main__":
    main()
