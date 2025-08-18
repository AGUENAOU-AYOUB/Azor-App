#!/usr/bin/env python3
import os
import sys

import time
import concurrent.futures
import threading
import requests
from urllib.parse import urlparse, parse_qs
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
            first, last = products[0][0], products[-1][0]
            print(f"[OK] {first}..{last}")
    else:
        print(f"[ERROR] {resp.text}")


def main():
    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json",
    })

    headers = session.headers.copy()

    processed = 0
    total_products = 0
    lock = threading.Lock()

    def progress_cb(count):
        nonlocal processed
        with lock:
            processed += count
            print(f"[PROGRESS] processed {processed}")

    def process_chunk(products):
        """Process a list of ``(product_id, price)`` tuples.

        We create a short‑lived session per worker so that the connection pool
        isn't shared across threads and to avoid hitting limits on some
        hosting providers that restrict the number of concurrent connections.
        """
        local_session = requests.Session()
        local_session.headers.update(headers)
        try:
            set_base_prices(local_session, products)
        finally:
            progress_cb(len(products))

    base_url = f"https://{DOMAIN}/admin/api/{API_VERSION}"
    page_info = None
    chunk = []
    # ``metafieldsSet`` only accepts up to 25 metafields per call.  Using more
    # would trigger errors such as "Exceeded the maximum number of metafields".
    CHUNK_SIZE = 25

    # Some execution environments (e.g. hosting providers) limit the number of
    # concurrent worker threads.  Keep the pool small to remain within those
    # limits and prevent "Exceeded the maximum worker limit" errors.
    MAX_WORKERS = 4

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
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
                total_products += 1
                if len(chunk) == CHUNK_SIZE:
                    executor.submit(process_chunk, chunk)
                    chunk = []

            link = resp.headers.get("Link", "")
            if link:
                links = requests.utils.parse_header_links(
                    link.rstrip('>').replace('>,<', ',<')
                )
                next_link = next((l for l in links if l.get('rel') == 'next'), None)
                if not next_link:
                    break
                next_url = next_link.get('url', '')
                page_info = parse_qs(urlparse(next_url).query).get('page_info', [None])[0]
                if not page_info:
                    break
            else:
                break

        if chunk:
            executor.submit(process_chunk, chunk)

    if processed != total_products:
        print(f"[DONE] Finished initializing base prices! Processed {processed} of {total_products} products (mismatch)")
    else:
        print(f"[DONE] Finished initializing base prices! Processed {processed} of {total_products} products")


if __name__ == "__main__":
    main()
