#!/usr/bin/env python3
import os
import json
import requests
import argparse
import time
from dotenv import load_dotenv

# 1) Load .env
load_dotenv()

# 2) Read credentials from environment
TOKEN       = os.getenv("API_TOKEN")
DOMAIN      = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")


def shopify_get(session, url, **kwargs):
    """GET request with basic retry handling for rate limits."""
    while True:
        resp = session.get(url, **kwargs)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def graphql_post(session, query, variables=None):
    """POST to the GraphQL endpoint with retry on 429."""
    url = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"
    payload = {"query": query, "variables": variables or {}}
    while True:
        resp = session.post(url, json=payload)
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


def get_base_price(session, product_id):
    query = """
    query GetBasePrice($id: ID!) {
      product(id: $id) {
        metafield(namespace: \"custom\", key: \"base_price\") {
          value
        }
      }
    }
    """
    resp = graphql_post(session, query, {"id": f"gid://shopify/Product/{product_id}"})
    if resp.ok:
        mf = resp.json()["data"]["product"]["metafield"]
        return mf["value"] if mf else None
    else:
        print(f"❌ base_price fetch {product_id}: {resp.text}")
        return None


def set_base_price(session, product_id, price):
    mutation = """
    mutation SetBase($mf: [MetafieldsSetInput!]!) {
      metafieldsSet(metafields: $mf) {
        metafields { id }
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
        data = resp.json()["data"]["metafieldsSet"]
        errors = data["userErrors"]
        if errors:
            for e in errors:
                print(f"❌ base_price {product_id}: {e['message']}")
            return False
        return True
    else:
        print(f"❌ base_price {product_id}: {resp.text}")
        return False

def fetch_all_variants(session, base_url):
    variants, page_info = [], None
    while True:
        params = {"limit": 250}
        if page_info:
            params["page_info"] = page_info
        resp = shopify_get(session, f"{base_url}/products.json", params=params)
        resp.raise_for_status()
        data = resp.json()
        for prod in data["products"]:
            for v in prod["variants"]:
                variants.append({
                    "product_id": prod["id"],
                    "variant_id": v["id"],
                    "original_price": v["price"]
                })
        link = resp.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        page_info = link.split("page_info=")[1].split(">")[0]
    return variants

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--percent", type=float, required=True,
                   help="Percentage to adjust prices by (e.g. 10 or -5)")
    args = p.parse_args()

    # 3) Setup session
    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json"
    })
    base_url = f"https://{DOMAIN}/admin/api/{API_VERSION}"

    # 4) Backup current prices
    backup_file = os.path.join(os.path.dirname(__file__), "shopify_backup.json")
    if not os.path.exists(backup_file):
        print("🔄 Fetching current variant prices...")
        variants = fetch_all_variants(session, base_url)
        with open(backup_file, "w", encoding="utf-8") as bf:
            json.dump(variants, bf, indent=2)
        print(f"✔️  Backup saved to {backup_file}")
    else:
        with open(backup_file, "r", encoding="utf-8") as bf:
            variants = json.load(bf)

    factor = 1 + args.percent / 100.0

    # 5) Apply percentage + tidy rounding
    mutation = """
    mutation BulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
      productVariantsBulkUpdate(productId: $productId, variants: $variants) {
        userErrors { field message }
      }
    }
    """
    updates_by_product = {}
    base_price_values = {}
    for v in variants:
        base = float(v["original_price"])
        newp = base * (1 + args.percent/100.0)
        tidy = round_to_tidy(newp)

        pid = v["product_id"]
        updates_by_product.setdefault(pid, [])
        updates_by_product[pid].append({
            "id": f"gid://shopify/ProductVariant/{v['variant_id']}",
            "price": tidy,
        })
        if pid not in base_price_values:
            base_price_values[pid] = tidy

    for pid, updates in updates_by_product.items():
        for i in range(0, len(updates), 50):
            batch = updates[i:i+50]
            resp = graphql_post(session, mutation, {
                "productId": f"gid://shopify/Product/{pid}",

                "variants": batch

            })
            if resp.ok:
                errors = resp.json()["data"]["productVariantsBulkUpdate"]["userErrors"]
                if errors:
                    for e in errors:
                        print(f"❌ {e['field']}: {e['message']}")
                for u in batch:

                    print(f"✅  {u['id'].split('/')[-1]} → {u['price']}")
            else:
                print(f"❌  bulk update failed: {resp.text}")

    for pid, price in base_price_values.items():
        existing = get_base_price(session, pid)
        if set_base_price(session, pid, price):
            new_val = get_base_price(session, pid)
            if new_val is not None:
                if existing is None:
                    print(f"🆕 base_price {pid} → {new_val}")
                else:
                    print(f"✅ base_price {pid} → {new_val}")
            else:
                print(f"❌ base_price {pid} not found after update")
        else:
            print(f"❌ base_price {pid} update failed")

    print("🎉 Finished updating!")

if __name__=="__main__":
    main()
