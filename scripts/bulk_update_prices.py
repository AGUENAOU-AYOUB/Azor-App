#!/usr/bin/env python3
"""Bulk update variant prices using Shopify's GraphQL bulk API."""
import os
import json
import time
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("API_TOKEN")
DOMAIN = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")

GRAPHQL_URL = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"


def graphql(session: requests.Session, query: str, variables=None):
    """Execute a GraphQL request with simple rate limit handling."""
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
    for i, u in enumerate(updates):
        alias = f"v{i}"
        gid = f"gid://shopify/ProductVariant/{u['id']}"
        parts.append(
            f"{alias}: productVariantUpdate(input: {{id: \"{gid}\", price: \"{u['price']}\"}}) {{ userErrors {{ field message }} }}"
        )
    return "mutation {\n" + "\n".join(parts) + "\n}"


def main():
    parser = argparse.ArgumentParser(description="Run a bulk price update from a JSON file")
    parser.add_argument("file", help="JSON file with variant id and price pairs")
    args = parser.parse_args()

    with open(args.file, encoding="utf-8") as f:
        updates = json.load(f)

    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json",
    })

    bulk_mutation = """
    mutation($mutation:String!){
      bulkOperationRunMutation(mutation:$mutation){
        bulkOperation { id status }
        userErrors { field message }
      }
    }
    """

    mutation = build_mutation(updates)
    print("▶️  Starting bulk mutation...")
    resp = graphql(session, bulk_mutation, {"mutation": mutation})
    print(json.dumps(resp, indent=2))

    op_id = resp["bulkOperationRunMutation"]["bulkOperation"]["id"]

    status_query = """
    query($id:ID!){
      node(id:$id){
        ... on BulkOperation{
          status
          errorCode
          objectCount
          createdAt
          completedAt
          url
        }
      }
    }
    """

    while True:
        stat = graphql(session, status_query, {"id": op_id})
        node = stat["node"]
        print(f"Status: {node['status']}")
        if node["status"] in {"COMPLETED", "FAILED", "CANCELED"}:
            print(json.dumps(node, indent=2))
            break
        time.sleep(5)

    print("✅ Done")


if __name__ == "__main__":
    main()
