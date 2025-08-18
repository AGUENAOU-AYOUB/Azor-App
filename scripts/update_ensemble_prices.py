#!/usr/bin/env python3
import os
import json
import time
import requests
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("API_TOKEN")
DOMAIN = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")


def shopify_get(session, url, **kwargs):
    """GET request with basic retry handling."""
    while True:
        resp = session.get(url, timeout=30, **kwargs)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def graphql_post(session, query, variables=None):
    """POST to Shopify GraphQL with retry on rate limits."""
    url = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"
    payload = {"query": query, "variables": variables or {}}
    while True:
        resp = session.post(url, json=payload, timeout=30)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def round_to_tidy(price: float) -> str:
    price_int = int(round(price))
    rem = price_int % 100
    base = price_int - rem
    opts = [base, base + 90, base + 100]
    tidy = min(opts, key=lambda x: abs(price_int - x))
    return f"{tidy:.2f}"


def main():
    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json",
    })

    sur_path = os.path.join(os.path.dirname(__file__), "..", "tempo solution", "variant_prices.json")
    with open(sur_path, encoding="utf-8") as f:
        surcharges = json.load(f)

    base_url = f"https://{DOMAIN}/admin/api/{API_VERSION}"

    updates_by_product = {}
    total = 0
    page_info = None
    while True:
        params = {"limit": 250, "fields": "id,tags,variants"}
        if page_info:
            params["page_info"] = page_info
        resp = shopify_get(session, f"{base_url}/products.json", params=params)
        resp.raise_for_status()
        data = resp.json()

        for prod in data.get("products", []):
            if "ensemble" not in prod.get("tags", ""):
                continue
            pid = prod["id"]
            base_price = float(prod["variants"][0]["price"])
            for v in prod["variants"]:
                collier = v.get("option1", "")
                bracelet = v.get("option2", "")
                price = base_price
                price += surcharges["colliers"].get(collier, 0)
                price += surcharges["bracelets"].get(bracelet, 0)
                tidy = round_to_tidy(price)
                updates_by_product.setdefault(pid, [])
                updates_by_product[pid].append({
                    "id": f"gid://shopify/ProductVariant/{v['id']}",
                    "price": tidy,
                })
                total += 1

        link = resp.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        page_info = link.split("page_info=")[1].split(">")[0]

    mutation = """
    mutation BulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
      productVariantsBulkUpdate(productId: $productId, variants: $variants) {
        userErrors { field message }
      }
    }
    """

    for pid, updates in updates_by_product.items():
        for i in range(0, len(updates), 50):
            batch = updates[i:i+50]
            resp = graphql_post(session, mutation, {
                "productId": f"gid://shopify/Product/{pid}",
                "variants": batch,
            })
            if resp.ok:
                errs = resp.json()["data"]["productVariantsBulkUpdate"]["userErrors"]
                if errs:
                    for e in errs:
                        print(f"[ERROR] {e['field']}: {e['message']}")
                for u in batch:
                    print(f"[OK] {u['id'].split('/')[-1]} → {u['price']}")
            else:
                print(f"[ERROR] bulk update failed: {resp.text}")

    print(f"[DONE] Updated {total} variants")


if __name__ == "__main__":
    main()

