#!/usr/bin/env python3
import os
import json
import requests
import argparse
import time

"""Adjust all variant prices by a percentage using a GraphQL bulk mutation."""
from dotenv import load_dotenv

# 1) Load .env
load_dotenv()

# 2) Read credentials from environment
TOKEN       = os.getenv("API_TOKEN")
DOMAIN      = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")

GRAPHQL_URL = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"


def shopify_get(session, url, **kwargs):
    """GET request with basic retry handling for rate limits."""
    while True:
        resp = session.get(url, **kwargs)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp



def graphql(session: requests.Session, query: str, variables=None):
    while True:
        resp = session.post(GRAPHQL_URL, json={"query": query, "variables": variables})
        if resp.status_code == 429:
            time.sleep(2)
            continue
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(data["errors"])
        return data["data"]

def build_mutation(updates):
    parts = []
    for i, item in enumerate(updates):
        alias = f"v{i}"
        gid = f"gid://shopify/ProductVariant/{item['id']}"
        parts.append(
            f"{alias}: productVariantUpdate(input: {{id: \"{gid}\", price: \"{item['price']}\"}}) {{ userErrors {{ field message }} }}"
        )
    inner = "\n".join(parts)
    return f"mutation {{\n{inner}\n}}"

def run_bulk(session, updates):
    if not updates:
        print("Nothing to update.")
        return
    mutation = build_mutation(updates)
    bulk_query = (
        "mutation($m:String!) {\n"
        "  bulkOperationRunMutation(mutation: $m) {\n"
        "    bulkOperation { id status }\n"
        "    userErrors { field message }\n"
        "  }\n"
        "}"
    )
    resp = graphql(session, bulk_query, {"m": mutation})
    print(json.dumps(resp, indent=2))
    op_id = resp["bulkOperationRunMutation"]["bulkOperation"]["id"]
    while True:
        status = graphql(
            session,
            "query($id:ID!){\n  node(id:$id){... on BulkOperation{status,errorCode,objectCount,createdAt,completedAt,url}}\n}",
            {"id": op_id},
        )
        node = status["node"]
        print(f"Status: {node['status']}")
        if node["status"] in {"COMPLETED", "FAILED", "CANCELED"}:
            print(json.dumps(node, indent=2))
            break
        time.sleep(5)

def round_to_tidy(price: float) -> str:
    price_int = int(round(price))
    rem = price_int % 100
    base = price_int - rem
    opts = [base, base + 90, base + 100]
    tidy = min(opts, key=lambda x: abs(price_int - x))
    return f"{tidy:.2f}"

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

    # 5) Apply percentage + tidy rounding using a bulk mutation
    updates = []
    for v in variants:
        base = float(v["original_price"])
        newp = base * (1 + args.percent/100.0)
        tidy = round_to_tidy(newp)
        updates.append({"id": v["variant_id"], "price": tidy})

    run_bulk(session, updates)
    print("🎉 Finished updating!")

if __name__=="__main__":
    main()
