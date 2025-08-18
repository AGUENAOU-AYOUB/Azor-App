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
    session.headers.update(
        {
            "X-Shopify-Access-Token": TOKEN,
            "Content-Type": "application/json",
        }
    )

    sur_path = os.path.join(
        os.path.dirname(__file__), "..", "tempo solution", "variant_prices.json"
    )
    with open(sur_path, encoding="utf-8") as f:
        surcharges = json.load(f)

    query = """
    query Ensemblers($cursor: String) {
      products(first: 250, query: "tag:ensemble", after: $cursor) {
        edges {
          cursor
          node {
            id
            variants(first: 250) {
              nodes { id price option1 option2 }
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
    """

    mutation = """
    mutation BulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
      productVariantsBulkUpdate(productId: $productId, variants: $variants) {
        userErrors { field message }
      }
    }
    """

    total = 0
    cursor = None
    while True:
        resp = graphql_post(session, query, {"cursor": cursor})
        resp.raise_for_status()
        data = resp.json()["data"]["products"]

        for edge in data["edges"]:
            product = edge["node"]
            pid = product["id"]
            base_price = float(product["variants"]["nodes"][0]["price"])

            updates = []
            for v in product["variants"]["nodes"]:
                collier = v.get("option1", "")
                bracelet = v.get("option2", "")
                price = base_price
                price += surcharges["colliers"].get(collier, 0)
                price += surcharges["bracelets"].get(bracelet, 0)
                tidy = round_to_tidy(price)
                updates.append({"id": v["id"], "price": tidy})

            for i in range(0, len(updates), 50):
                batch = updates[i : i + 50]
                resp_u = graphql_post(
                    session,
                    mutation,
                    {"productId": pid, "variants": batch},
                )
                if resp_u.ok:
                    errs = resp_u.json()["data"]["productVariantsBulkUpdate"][
                        "userErrors"
                    ]
                    if errs:
                        for e in errs:
                            print(f"[ERROR] {e['field']}: {e['message']}")
                    for u in batch:
                        print(f"[OK] {u['id'].split('/')[-1]} → {u['price']}")
                else:
                    print(f"[ERROR] bulk update failed: {resp_u.text}")

            total += len(updates)

        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]

    print(f"[DONE] Updated {total} variants")


if __name__ == "__main__":
    main()

