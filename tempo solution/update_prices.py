#!/usr/bin/env python3
"""
update_prices.py  –  one-shot Shopify variant price updater
Now submits a single GraphQL bulk mutation for all variant updates.
────────────────────────────────────────────────────────────
 • Picks every product tagged CHAINE_UPDATE  +  bracelet/collier
 • Reads base price from metafield   custom.base_price
 • Adds surcharge from variant_prices.json
 • BUT:  "Forsat S" surcharge is forced to 0.0  → price = base_price
 • Rounds:  …xx.00  if decimal < 0.5   else  …xx.90
"""

import os
import sys
import json
import math
import time
import textwrap
import requests
from dotenv import load_dotenv

# ─────────── ENV / CONFIG ───────────
load_dotenv()                                   # expect .env in same dir
SHOP_DOMAIN = os.getenv("SHOP_DOMAIN")          # azorjewelry.myshopify.com
API_TOKEN   = os.getenv("API_TOKEN")            # shpat_****
API_VERSION = os.getenv("API_VERSION", "2024-04")

GRAPHQL_URL = f"https://{SHOP_DOMAIN}/admin/api/{API_VERSION}/graphql.json"

HEADERS = {
    "X-Shopify-Access-Token": API_TOKEN,
    "Content-Type": "application/json"
}

SURCHARGE_FILE = os.path.join(os.path.dirname(__file__), "variant_prices.json")
# ─────────────────────────────────────


# ---------- helpers ----------
def load_surcharges():
    with open(SURCHARGE_FILE, encoding="utf-8") as f:
        return json.load(f)


def get(endpoint, params=None):
    url = f"https://{SHOP_DOMAIN}/admin/api/{API_VERSION}/{endpoint}"
    while True:
        r = requests.get(url, headers=HEADERS, params=params)
        if r.status_code == 429:
            time.sleep(2)
            continue
        r.raise_for_status()
        return r



def graphql(query: str, variables=None):
    while True:
        r = requests.post(GRAPHQL_URL, headers=HEADERS, json={"query": query, "variables": variables})
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
    inner = "\n".join(parts)
    return f"mutation {{\n{inner}\n}}"

def run_bulk(updates):
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
    resp = graphql(bulk_query, {"m": mutation})
    print(json.dumps(resp, indent=2))
    op_id = resp["bulkOperationRunMutation"]["bulkOperation"]["id"]
    while True:
        status = graphql(
            "query($id:ID!){\n  node(id:$id){... on BulkOperation{status,errorCode,objectCount,createdAt,completedAt,url}}\n}",
            {"id": op_id},
        )
        node = status["node"]
        print(f"Status: {node['status']}")
        if node["status"] in {"COMPLETED", "FAILED", "CANCELED"}:
            print(json.dumps(node, indent=2))
            break
        time.sleep(5)


def paginate_products():
    page = None
    while True:
        params = {"limit": 250, **({"page_info": page} if page else {})}
        r = get("products.json", params)
        for p in r.json()["products"]:
            yield p

        link = r.headers.get("Link", "")
        nxt = None
        for part in link.split(","):
            if 'rel="next"' in part:
                nxt = part.split(";")[0].split("page_info=")[1].strip("<> ")
        if not nxt:
            break
        page = nxt


def base_price(product_id):
    r = get(f"products/{product_id}/metafields.json")
    for mf in r.json()["metafields"]:
        if mf["namespace"] == "custom" and mf["key"] == "base_price":
            return float(mf["value"])
    return None


def smart_round(x: float) -> float:
    return math.floor(x) + (0.9 if (x % 1) >= 0.5 else 0)


# ---------- main ----------
def main():
    if not SHOP_DOMAIN or not API_TOKEN:
        sys.exit("❌  SHOP_DOMAIN / API_TOKEN missing in .env")

    surcharges = load_surcharges()
    updated = 0
    updates = []

    for prod in paginate_products():
        tags = {t.strip().lower() for t in prod["tags"].split(",")}
        if "chaine_update" not in tags:
            continue

        cat = "bracelets" if "bracelet" in tags else ("colliers" if "collier" in tags else None)
        if not cat:
            print(f"• Skip {prod['title']} (no bracelet/collier tag)")
            continue

        bp = base_price(prod["id"])
        if bp is None:
            print(f"• Skip {prod['title']} (missing base_price)")
            continue

        print(f"\n→  {prod['title']}  [{cat}]  base={bp}")
        for v in prod["variants"]:
            # grab chain name from option1/2/3
            chain = next(
                (opt for opt in (v.get("option1"), v.get("option2"), v.get("option3"))
                 if opt and opt in surcharges[cat]),
                None
            )
            if chain is None:
                print(f"   └─ {v['title']:<25} not in surcharge list, skipped")
                continue

            # Forsat S rule
            surcharge = 0.0 if chain == "Forsat S" else surcharges[cat][chain]
            new_price = smart_round(bp + surcharge)

            if float(v["price"]) == new_price:
                print(f"   └─ {chain:<10} already {new_price}")
                continue

            updates.append({"id": v["id"], "price": str(new_price)})
            print(f"   └─ {chain:<10} → {new_price}")

        updated += 1

    run_bulk(updates)
    print(f"\nDone. Updated {updated} product(s).")


if __name__ == "__main__":
    print(textwrap.dedent(f"""
        ─────────────────────────────────────────────
        Shopify Variant Price Updater  –  Forsat S = base_price
        Store : {SHOP_DOMAIN}
        API   : {API_VERSION}
        ─────────────────────────────────────────────
    """))
    main()
