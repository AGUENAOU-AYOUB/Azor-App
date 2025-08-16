#!/usr/bin/env python3
import os
import sys

import time
import concurrent.futures
import requests
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")
TOKEN       = os.getenv("API_TOKEN")
DOMAIN      = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")


def shopify_get(session, url, **kwargs):

    while True:
        try:
            resp = session.get(url, timeout=30, **kwargs)
        except requests.exceptions.ReadTimeout:
            print(f"[ERROR] {url}: request timed out")
            time.sleep(2)
            continue
        except requests.exceptions.ConnectionError:
            print(f"[ERROR] {url}: connection failed")
            time.sleep(2)
            continue
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def graphql_post(session, query, variables=None):

    url = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"
    payload = {"query": query, "variables": variables or {}}
    while True:
        try:
            resp = session.post(url, json=payload, timeout=30)
        except requests.exceptions.ReadTimeout:
            prod_id = None
            try:
                prod_id = variables["mf"][0]["ownerId"].split("/")[-1]
            except Exception:
                pass
            if prod_id:
                print(f"[ERROR] {prod_id}: request timed out")
            else:
                print("[ERROR] request timed out")
            time.sleep(2)
            continue
        except requests.exceptions.ConnectionError:
            prod_id = None
            try:
                prod_id = variables["mf"][0]["ownerId"].split("/")[-1]
            except Exception:
                pass
            if prod_id:
                print(f"[ERROR] {prod_id}: request failed")
            else:
                print("[ERROR] request failed")
            time.sleep(2)
            continue
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def set_base_prices(session, products):
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
                "ownerId": f"gid://shopify/Product/{pid}",
                "namespace": "custom",
                "key": "base_price",
                "type": "number_decimal",
                "value": str(price),
            }
            for pid, price in products
        ]
    }
    resp = graphql_post(session, mutation, variables)
    if resp.ok:
        errs = resp.json()["data"]["metafieldsSet"]["userErrors"]
        if errs:
            for e in errs:
                idx = None
                try:
                    idx = int(e.get("field", [])[1])
                except Exception:
                    pass
                prod_id = products[idx][0] if idx is not None and 0 <= idx < len(products) else "?"
                print(f"[ERROR] {prod_id}: {e['message']}")
        else:
            for pid, price in products:
                print(f"[OK] {pid} -> {price}")
    else:
        print(f"[ERROR] {resp.text}")


def main():
    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json",
    })

    headers = session.headers.copy()

    def process_chunk(products):
        local_session = requests.Session()
        local_session.headers.update(headers)
        set_base_prices(local_session, products)

    base_url = f"https://{DOMAIN}/admin/api/{API_VERSION}"
    page_info = None
    chunk = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        while True:
            params = {"limit": 250}

            if page_info:
                params["page_info"] = page_info
            resp = shopify_get(session, f"{base_url}/products.json", params=params)
            resp.raise_for_status()
            data = resp.json()

            for prod in data.get("products", []):
                price = prod["variants"][0]["price"]
                chunk.append((prod["id"], price))
                if len(chunk) == 25:
                    executor.submit(process_chunk, chunk)
                    chunk = []

            link = resp.headers.get("Link", "")
            if 'rel="next"' not in link:
                break
            page_info = link.split("page_info=")[1].split(">")[0]

        if chunk:
            executor.submit(process_chunk, chunk)

    print("[DONE] Finished initializing base prices!")


if __name__ == "__main__":
    main()
