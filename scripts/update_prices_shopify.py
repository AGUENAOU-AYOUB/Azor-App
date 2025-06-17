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


def shopify_put(session, url, **kwargs):
    """PUT request with basic retry handling for rate limits."""
    while True:
        resp = session.put(url, **kwargs)
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

    # 5) Apply percentage + tidy rounding
    for v in variants:
        base = float(v["original_price"])
        newp = base * (1 + args.percent/100.0)
        tidy = round_to_tidy(newp)

        url = f"{base_url}/variants/{v['variant_id']}.json"
        payload = {"variant": {"id": v["variant_id"], "price": tidy}}
        resp = shopify_put(session, url, json=payload)
        if resp.ok:
            print(f"✅  {v['variant_id']} → {tidy}")
        else:
            print(f"❌  {v['variant_id']} failed: {resp.text}")

    print("🎉 Finished updating!")

if __name__=="__main__":
    main()
