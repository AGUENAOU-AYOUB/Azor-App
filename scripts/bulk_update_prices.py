#!/usr/bin/env python3
"""Bulk variant price updater using Shopify's GraphQL Bulk Operation."""
import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("API_TOKEN")
DOMAIN = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")

GRAPHQL_URL = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"

session = requests.Session()
session.headers.update({
    "X-Shopify-Access-Token": TOKEN,
    "Content-Type": "application/json"
})


def graphql(query: str, variables=None):
    while True:
        r = session.post(GRAPHQL_URL, json={"query": query, "variables": variables})
        if r.status_code == 429:
            time.sleep(2)
            continue
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise RuntimeError(data["errors"])
        return data["data"]


def build_mutation(updates):
    parts = []
    for i, u in enumerate(updates):
        alias = f"v{i}"
        gid = f"gid://shopify/ProductVariant/{u['id']}"
        parts.append(
            f"{alias}: productVariantUpdate(input: {{id: \"{gid}\", price: \"{u['price']}\"}}) {{ userErrors {{ field message }} }}"
        )
    return "mutation {\n" + "\n".join(parts) + "\n}"


def run_bulk(updates):
    if not updates:
        print("Nothing to update.")
        return
    mutation = build_mutation(updates)
    bulk_query = (
        "mutation($m:String!){\n"
        "  bulkOperationRunMutation(mutation:$m){\n"
        "    bulkOperation{ id status }\n"
        "    userErrors{ field message }\n"
        "  }\n"
        "}"
    )
    resp = graphql(bulk_query, {"m": mutation})
    print(json.dumps(resp, indent=2))
    op_id = resp["bulkOperationRunMutation"]["bulkOperation"]["id"]
    status_q = (
        "query($id:ID!){\n  node(id:$id){... on BulkOperation{status,errorCode,objectCount,createdAt,completedAt,url}}\n}"
    )
    while True:
        status = graphql(status_q, {"id": op_id})
        node = status["node"]
        print(f"Status: {node['status']}")
        if node["status"] in {"COMPLETED", "FAILED", "CANCELED"}:
            print(json.dumps(node, indent=2))
            break
        time.sleep(5)


def main():
    if len(sys.argv) < 2:
        print("Usage: bulk_update_prices.py updates.json")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        updates = json.load(f)
    run_bulk(updates)


if __name__ == "__main__":
    main()
