#!/usr/bin/env python3
import os
import json
import requests
from dotenv import load_dotenv
import argparse

# 1) Load .env
load_dotenv()

# 2) Read credentials
TOKEN       = os.getenv("API_TOKEN")
DOMAIN      = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")

def main():
    p = argparse.ArgumentParser()
    p.parse_args()

    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": TOKEN,
        "Content-Type": "application/json"
    })
    base_url = f"https://{DOMAIN}/admin/api/{API_VERSION}"

    backup_file = os.path.join(os.path.dirname(__file__), "shopify_backup.json")
    if not os.path.exists(backup_file):
        print("❌  No backup found. Cannot reset.")
        return

    variants = json.load(open(backup_file, "r", encoding="utf-8"))
    for v in variants:
        url = f"{base_url}/variants/{v['variant_id']}.json"
        payload = {"variant": {"id": v["variant_id"], "price": v["original_price"]}}
        resp = session.put(url, json=payload)
        if resp.ok:
            print(f"🔄  {v['variant_id']} → {v['original_price']}")
        else:
            print(f"❌  reset {v['variant_id']}: {resp.text}")

    print("✅  All prices reset.")

if __name__=="__main__":
    main()
