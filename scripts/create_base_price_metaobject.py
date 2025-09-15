#!/usr/bin/env python3
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("API_TOKEN")
DOMAIN = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")


def graphql_request(session, query, variables=None):
    url = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"
    payload = {"query": query, "variables": variables or {}}
    while True:
        resp = session.post(url, json=payload, timeout=30)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def main():
    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json",
    })

    mutation = """
    mutation CreateDef($def: MetaobjectDefinitionCreateInput!) {
      metaobjectDefinitionCreate(definition: $def) {
        metaobjectDefinition { id }
        userErrors { field message }
      }
    }
    """
    variables = {
        "def": {
            "name": "base_price",
            "type": "base_price",
            "fieldDefinitions": [
                {
                    "name": "Product",
                    "key": "product",
                    "type": "reference",
                    "referenceType": "PRODUCT",
                },
                {
                    "name": "Price",
                    "key": "price",
                    "type": "number_decimal",
                },
            ],
        }
    }

    resp = graphql_request(session, mutation, variables)
    if resp.ok:
        data = resp.json().get("data", {}).get("metaobjectDefinitionCreate", {})
        errs = data.get("userErrors")
        if errs:
            print("[ERROR]", errs)
        else:
            mid = data.get("metaobjectDefinition", {}).get("id")
            print(f"[OK] Definition created (id={mid})")
    else:
        print(f"[ERROR] {resp.status_code} {resp.text}")


if __name__ == "__main__":
    main()
