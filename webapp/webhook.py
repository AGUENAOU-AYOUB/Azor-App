import os
import hmac
import hashlib
import base64
import requests
from flask import Blueprint, request
from . import csrf

API_VERSION = os.getenv("API_VERSION", "2024-04")

webhook_bp = Blueprint("webhook", __name__)


def _verify_webhook(body: bytes, hmac_header: str) -> bool:
    secret = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")
    if not secret or not hmac_header:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, hmac_header)


def _shopify_session() -> requests.Session:
    token = os.getenv("API_TOKEN")
    session = requests.Session()
    session.headers.update({
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    })
    return session


def _update_variant_prices(product_id: int, price: str) -> None:
    session = _shopify_session()
    domain = os.getenv("SHOP_DOMAIN")
    base_url = f"https://{domain}/admin/api/{API_VERSION}"
    resp = session.get(f"{base_url}/products/{product_id}.json", timeout=30)
    resp.raise_for_status()
    variants = [v["id"] for v in resp.json().get("product", {}).get("variants", [])]
    if not variants:
        return
    mutation = """
    mutation BulkUpdate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
      productVariantsBulkUpdate(productId: $productId, variants: $variants) {
        userErrors { field message }
      }
    }
    """
    variables_base = {"productId": f"gid://shopify/Product/{product_id}"}
    chunks = [variants[i:i+50] for i in range(0, len(variants), 50)]
    for chunk in chunks:
        vars_payload = {
            **variables_base,
            "variants": [
                {
                    "id": f"gid://shopify/ProductVariant/{vid}",
                    "price": price,
                    "compareAtPrice": price,
                }
                for vid in chunk
            ],
        }
        resp = session.post(
            f"https://{domain}/admin/api/{API_VERSION}/graphql.json",
            json={"query": mutation, "variables": vars_payload},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        errors = data.get("productVariantsBulkUpdate", {}).get("userErrors")
        if errors:
            raise Exception(f"Bulk update errors: {errors}")


@webhook_bp.route("/webhook/metafield", methods=["POST"])
@csrf.exempt
def metafield_update():
    if not _verify_webhook(request.data, request.headers.get("X-Shopify-Hmac-SHA256", "")):
        return "Unauthorized", 401
    data = request.get_json() or {}
    if data.get("namespace") == "custom" and data.get("key") == "base_price":
        price = str(data.get("value"))
        product_id = data.get("owner_id")
        try:
            _update_variant_prices(product_id, price)
        except Exception as exc:
            print(f"Webhook error: {exc}")
            return "", 500
    return "", 200
