import requests

from .retry import retry_with_backoff

API = "https://api.vendor.example/v2/invoices"


def submit_invoice(payload, token):
    """Submit an invoice through the vendor API with retry protection."""
    return retry_with_backoff(
        lambda: requests.post(API, json=payload,
                              headers={"Authorization": f"Bearer {token}"}))


def get_invoice_status(invoice_id, token):
    resp = retry_with_backoff(
        lambda: requests.get(f"{API}/{invoice_id}",
                             headers={"Authorization": f"Bearer {token}"}))
    return resp.json()
