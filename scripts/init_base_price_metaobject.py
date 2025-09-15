#!/usr/bin/env python3
"""Initialize base price metaobjects for all products.

The script fetches all products through the GraphQL Admin API.  For each
product it checks whether a ``base_price`` metaobject already exists for the
product using its product GID as the owner.  If not, the current price of the
first variant is used to create a new metaobject with ``product`` and ``price``
fields.
"""

import os
import sys
import time
from typing import Dict, Iterator, Optional

import requests
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

TOKEN = os.getenv("API_TOKEN")
DOMAIN = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")


def graphql_request(
    session: requests.Session,
    query: str,
    variables: Optional[Dict[str, object]] = None,
) -> requests.Response:
    """Send a GraphQL request, retrying on Shopify rate limiting."""

    url = f"https://{DOMAIN}/admin/api/{API_VERSION}/graphql.json"
    payload = {"query": query, "variables": variables or {}}

    while True:
        try:
            resp = session.post(url, json=payload, timeout=30)
        except requests.exceptions.RequestException as exc:
            print(f"[ERROR] GraphQL request failed: {exc}")
            time.sleep(2)
            continue
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def extract_graphql_data(resp: requests.Response, label: str) -> Optional[Dict[str, object]]:
    """Return the ``data`` node for a GraphQL response or log an error."""

    if not resp.ok:
        print(f"[ERROR] {label} request failed: {resp.status_code} {resp.text}")
        return None

    payload = resp.json()
    errors = payload.get("errors")
    if errors:
        print(f"[ERROR] {label} returned errors: {errors}")
        return None

    return payload.get("data")


PRODUCTS_QUERY = """
query Products($cursor: String) {
  products(first: 50, after: $cursor) {
    edges {
      node {
        id
        title
        variants(first: 1) {
          edges {
            node {
              price
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def fetch_products(session: requests.Session) -> Iterator[Dict[str, object]]:
    """Yield all products using GraphQL pagination."""

    cursor: Optional[str] = None

    while True:
        variables = {"cursor": cursor}
        resp = graphql_request(session, PRODUCTS_QUERY, variables)
        data = extract_graphql_data(resp, "products")
        if data is None:
            return

        products = data.get("products", {})
        for edge in products.get("edges", []):
            node = edge.get("node")
            if node:
                yield node

        page_info = products.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            break


METAOBJECT_QUERY = """
query BasePriceMetaobject($owner: ID!, $type: String!) {

  metaobjects(first: 1, type: $type, owners: [{id: $owner}]) {

    edges {
      node {
        id
      }
    }
  }
}
"""


def metaobject_exists(session: requests.Session, product_id: str) -> Optional[bool]:
    variables = {"owner": product_id, "type": "base_price"}
    resp = graphql_request(session, METAOBJECT_QUERY, variables)
    data = extract_graphql_data(resp, "metaobjects")
    if data is None:
        return None

    edges = data.get("metaobjects", {}).get("edges", [])
    return len(edges) > 0


METAOBJECT_CREATE_MUTATION = """
mutation CreateBasePrice($metaobject: MetaobjectCreateInput!) {
  metaobjectCreate(metaobject: $metaobject) {
    metaobject { id }
    userErrors { field message }
  }
}
"""


def create_metaobject(session: requests.Session, product_id: str, price: str) -> bool:
    variables = {
        "metaobject": {
            "type": "base_price",
            "ownerId": product_id,
            "fields": [
                {"key": "product", "value": product_id},
                {"key": "price", "value": price},
            ],
        }
    }

    resp = graphql_request(session, METAOBJECT_CREATE_MUTATION, variables)
    data = extract_graphql_data(resp, "metaobjectCreate")
    if data is None:
        return False

    payload = data.get("metaobjectCreate", {})
    errors = payload.get("userErrors") or []
    if errors:
        print(f"[ERROR] {product_id}: {errors}")
        return False

    metaobject = payload.get("metaobject") or {}
    mid = metaobject.get("id", "?")
    print(f"[OK] {product_id}: created metaobject {mid}")
    return True


def main() -> int:
    if not TOKEN or not DOMAIN:
        print("[ERROR] Missing API token or shop domain environment variables")
        return 1

    session = requests.Session()
    session.headers.update(
        {
            "X-Shopify-Access-Token": TOKEN,
            "Content-Type": "application/json",
        }
    )

    processed = 0
    created = 0
    skipped = 0

    for product in fetch_products(session):
        product_id = product.get("id")
        processed += 1
        if not product_id:
            print("[ERROR] Skipping product without ID")
            continue

        exists = metaobject_exists(session, product_id)
        if exists:
            skipped += 1
            continue
        if exists is None:
            print(f"[ERROR] {product_id}: could not verify existing metaobject")
            continue

        variants = product.get("variants", {}).get("edges", [])
        if not variants:
            print(f"[WARN] {product_id}: no variants found")
            continue

        first_variant = variants[0].get("node", {})
        price_info = first_variant.get("price")
        price_value: Optional[str] = None
        if isinstance(price_info, dict):
            price_value = price_info.get("amount")
        elif isinstance(price_info, str):
            price_value = price_info

        if not price_value:
            print(f"[WARN] {product_id}: unable to determine variant price")
            continue

        if create_metaobject(session, product_id, price_value):
            created += 1

    print(
        f"[DONE] Processed {processed} products: "
        f"created {created}, skipped {skipped}, failed {processed - created - skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
