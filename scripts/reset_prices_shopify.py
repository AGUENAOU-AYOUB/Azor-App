#!/usr/bin/env python3
import os
import json
import requests
from dotenv import load_dotenv
import argparse
import time

# 1) Load .env
load_dotenv()

# 2) Read credentials
TOKEN       = os.getenv("API_TOKEN")
DOMAIN      = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")


def graphql_post(session, query, variables=None):
    """POST to Shopify's GraphQL API with basic retry for rate limits."""
    url = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"
    payload = {"query": query, "variables": variables or {}}
    while True:
        resp = session.post(url, json=payload)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp

def main():
    p = argparse.ArgumentParser()
    p.parse_args()

    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json"
    })

    backup_file = os.path.join(os.path.dirname(__file__), "shopify_backup.json")
    if not os.path.exists(backup_file):
        print("❌  No backup found. Cannot reset.")
        return

    variants = json.load(open(backup_file, "r", encoding="utf-8"))

    mutation = """
    mutation BulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
      productVariantsBulkUpdate(productId: $productId, variants: $variants) {
        userErrors { field message }
      }
    }
    """

    batches = {}


    def send_batch(pid, items):
        resp = graphql_post(session, mutation, {
            "productId": f"gid://shopify/Product/{pid}",
            "variants": items
        })
        if resp.ok:
            errors = resp.json()["data"]["productVariantsBulkUpdate"]["userErrors"]
            for e in errors:
                print(f"❌ {e['field']}: {e['message']}")
            for u in items:
                print(f"🔄  {u['id'].split('/')[-1]} → {u['price']}")
        else:
            print(f"❌  bulk update failed: {resp.text}")

    for v in variants:
        pid = v["product_id"]

        batches.setdefault(pid, [])
        batches[pid].append({
            "id": f"gid://shopify/ProductVariant/{v['variant_id']}",
            "price": v["original_price"],
        })
        if len(batches[pid]) == 50:
            send_batch(pid, batches[pid])
            batches[pid] = []

    for pid, batch in batches.items():
        if batch:
            send_batch(pid, batch)


    print("✅  All prices reset.")

if __name__=="__main__":
    main()
