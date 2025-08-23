#!/usr/bin/env python3
import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("API_TOKEN")
DOMAIN = os.getenv("SHOP_DOMAIN")
API_VERSION = os.getenv("API_VERSION", "2024-04")
APP_BASE_URL = os.getenv("APP_BASE_URL")

if not APP_BASE_URL:
    print("APP_BASE_URL is not set")
    sys.exit(1)


def shopify_request(session, method, url, **kwargs):
    while True:
        resp = session.request(method, url, timeout=30, **kwargs)
        if resp.status_code == 429:
            time.sleep(2)
            continue
        return resp


def main():
    session = requests.Session()
    session.headers.update(
        {
            "X-Shopify-Access-Token": TOKEN,
            "Content-Type": "application/json",
        }
    )
    base_url = f"https://{DOMAIN}/admin/api/{API_VERSION}"
    address = f"{APP_BASE_URL.rstrip('/')}/webhook/metafield"

    # Check existing webhooks
    resp = shopify_request(
        session,
        "get",
        f"{base_url}/webhooks.json",
        params={"topic": "metafields/update"},
    )
    if resp.ok:
        for hook in resp.json().get("webhooks", []):
            if hook.get("address") == address:
                print(f"[OK] Webhook already registered (id={hook.get('id')})")
                return

    payload = {
        "webhook": {
            "topic": "metafields/update",
            "address": address,
            "format": "json",
        }
    }
    resp = shopify_request(
        session, "post", f"{base_url}/webhooks.json", json=payload
    )
    if resp.ok:
        wid = resp.json().get("webhook", {}).get("id")
        print(f"[OK] Registered webhook (id={wid})")
    else:
        print(f"[ERROR] {resp.status_code} {resp.text}")
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            errors = {}
            try:
                errors = resp.json().get("errors", {})
            except ValueError:
                pass
            topic_error = errors.get("topic")
            if topic_error:
                print(
                    f"[INFO] {topic_error} — ensure the app has required scopes (e.g., read/write_metafields)"
                )
            raise


if __name__ == "__main__":
    main()
