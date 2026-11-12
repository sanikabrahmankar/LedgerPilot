import os

import requests
from requests.auth import HTTPBasicAuth

PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox").lower()
PAYPAL_API_BASE = os.getenv(
    "PAYPAL_API_BASE",
    "https://api-m.paypal.com" if PAYPAL_MODE == "live" else "https://api-m.sandbox.paypal.com",
)
PAYPAL_CURRENCY = os.getenv("PAYPAL_CURRENCY", "USD")
REQUEST_TIMEOUT = 30


def get_paypal_access_token():
    """Authenticates with PayPal to receive a temporary OAuth2 token."""
    client_id = os.getenv("PAYPAL_CLIENT_ID")
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are not set.")

    response = requests.post(
        f"{PAYPAL_API_BASE}/v1/oauth2/token",
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={"grant_type": "client_credentials"},
        auth=HTTPBasicAuth(client_id, client_secret),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def execute_payout(invoice_data, receiver_email=None):
    """Triggers an automated payout to the vendor via the PayPal Payouts API."""
    receiver = receiver_email or os.getenv("PAYPAL_RECEIVER_EMAIL")
    if not receiver:
        raise RuntimeError("No PayPal receiver email: set vendor paypal_email or PAYPAL_RECEIVER_EMAIL.")

    try:
        amount = float(invoice_data.get("total_amount", 0))
    except (TypeError, ValueError):
        raise ValueError("Invoice total_amount is not a valid number.")
    if amount <= 0:
        raise ValueError("Invoice total_amount must be greater than zero.")

    invoice_number = str(invoice_data.get("invoice_number") or "UNKNOWN")
    # Deterministic batch id: PayPal rejects a repeated sender_batch_id, which
    # protects against double payouts on retries and double clicks.
    batch_id = f"LP_{invoice_data.get('_id')}" if invoice_data.get("_id") else f"LP_{invoice_number}_{os.urandom(4).hex()}"

    token = get_paypal_access_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "PayPal-Request-Id": batch_id,
    }
    payload = {
        "sender_batch_header": {
            "sender_batch_id": batch_id,
            "email_subject": "LedgerPilot: Invoice Payment Processed",
            "email_message": f"Your payment for invoice {invoice_number} has been completed.",
        },
        "items": [
            {
                "recipient_type": "EMAIL",
                "amount": {"value": f"{amount:.2f}", "currency": PAYPAL_CURRENCY},
                "note": "Automated payout via LedgerPilot AI.",
                "sender_item_id": invoice_number[:30],
                "receiver": receiver,
            }
        ],
    }

    response = requests.post(
        f"{PAYPAL_API_BASE}/v1/payments/payouts",
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def verify_webhook_signature(headers, event_body):
    """Verifies a webhook really came from PayPal (verify-webhook-signature API)."""
    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID")
    if not webhook_id:
        raise RuntimeError("PAYPAL_WEBHOOK_ID is not set.")

    token = get_paypal_access_token()
    payload = {
        "auth_algo": headers.get("PAYPAL-AUTH-ALGO"),
        "cert_url": headers.get("PAYPAL-CERT-URL"),
        "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID"),
        "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG"),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME"),
        "webhook_id": webhook_id,
        "webhook_event": event_body,
    }
    response = requests.post(
        f"{PAYPAL_API_BASE}/v1/notifications/verify-webhook-signature",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("verification_status") == "SUCCESS"