#!/usr/bin/env python3
"""Bulk update variant prices using Shopify's GraphQL bulk API."""
import os
import json
import time
import argparse
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv("API_TOKEN")
DOMAIN = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")

GRAPHQL_URL = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"


def graphql(session: requests.Session, query: str, variables=None):
    """Helper to perform a GraphQL request with basic rate limit handling."""
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
        price = item['price']
        parts.append(
            f"{alias}: productVariantUpdate(input: {{id: \"{gid}\", price: \"{price}\"}}) {{ userErrors {{ field message }} }}"
        )
    inner = "\n".join(parts)
    return f"mutation {{\n{inner}\n}}"


def main():
    ap = argparse.ArgumentParser(description="Run a bulk price update")
    ap.add_argument("file", help="JSON file containing variant id/price pairs")
    args = ap.parse_args()

    with open(args.file, encoding="utf-8") as f:
        updates = json.load(f)

    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json",
    })

    mutation = build_mutation(updates)
    bulk_query = (
        "mutation($m:String!) {\n"
        "  bulkOperationRunMutation(mutation: $m) {\n"
        "    bulkOperation { id status }\n"
        "    userErrors { field message }\n"
        "  }\n"
        "}"
    )

    print("▶️  Starting bulk operation...")
    resp = graphql(session, bulk_query, {"m": mutation})
    print(json.dumps(resp, indent=2))

    op_id = resp["bulkOperationRunMutation"]["bulkOperation"]["id"]
    while True:
        status_data = graphql(
            session,
            "query($id:ID!){\n  node(id:$id){... on BulkOperation{status,errorCode,objectCount,createdAt,completedAt,url}}\n}",
            {"id": op_id},
        )
        node = status_data["node"]
        print(f"Status: {node['status']}")
        if node["status"] in {"COMPLETED", "FAILED", "CANCELED"}:
            print(json.dumps(node, indent=2))
            break
        time.sleep(5)

    print("✅  Finished bulk update")


if __name__ == "__main__":
    main()
