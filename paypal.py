
import os
import uuid
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv


# ==================================================
# CONFIGURATION
# ==================================================

load_dotenv()

CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")

BASE_URL = (
    os.getenv("PAYPAL_BASE_URL", "")
    .strip()
    .rstrip("/")
)

APP_BASE_URL = (
    os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")
    .strip()
    .rstrip("/")
)

CURRENCY = "USD"
TIMEOUT = 20

ALLOWED_BASE_URLS = {
    "https://api-m.sandbox.paypal.com",
    "https://api-m.paypal.com",
}


# ==================================================
# CONFIGURATION VALIDATION
# ==================================================

def validate_config():

    if not CLIENT_ID or not CLIENT_SECRET:
        raise ValueError("PayPal credentials missing in environment.")

    if BASE_URL not in ALLOWED_BASE_URLS:
        raise ValueError(
            "Invalid PAYPAL_BASE_URL. "
            "Use the official PayPal Sandbox or Live API URL."
        )

    parsed_url = urlsplit(APP_BASE_URL)

    is_local = (
        parsed_url.scheme == "http"
        and parsed_url.hostname in ("127.0.0.1", "localhost")
    )

    is_production = (
        parsed_url.scheme == "https"
        and bool(parsed_url.hostname)
    )

    if not (is_local or is_production):
        raise ValueError(
            "APP_BASE_URL must use HTTPS in deployment "
            "or localhost HTTP during local testing."
        )

    if parsed_url.username or parsed_url.password:
        raise ValueError("APP_BASE_URL must not contain credentials.")

    if parsed_url.query or parsed_url.fragment:
        raise ValueError(
            "APP_BASE_URL must not contain query parameters or fragments."
        )


# ==================================================
# AMOUNT VALIDATION
# ==================================================

def format_amount(amount):

    try:
        value = Decimal(str(amount))

        if not value.is_finite() or value <= 0:
            raise ValueError("Invalid payment amount.")

        if value != value.quantize(Decimal("0.01")):
            raise ValueError(
                "Payment amount cannot exceed two decimal places."
            )

        return format(value, ".2f")

    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("Invalid payment amount.") from error


# ==================================================
# PAYPAL ACCESS TOKEN
# ==================================================

def get_access_token():

    validate_config()

    response = requests.post(
        f"{BASE_URL}/v1/oauth2/token",
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        headers={
            "Accept": "application/json",
            "Accept-Language": "en_US"
        },
        timeout=TIMEOUT
    )

    response.raise_for_status()

    data = response.json()
    access_token = data.get("access_token")

    if not access_token:
        raise RuntimeError("PayPal did not return an access token.")

    return access_token


# ==================================================
# CREATE PAYPAL ORDER
# ==================================================

def create_order(amount):

    formatted_amount = format_amount(amount)
    token = get_access_token()

    response = requests.post(
        f"{BASE_URL}/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "PayPal-Request-Id": uuid.uuid4().hex
        },
        json={
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "description": "Guardian Pay Test Payment",
                    "amount": {
                        "currency_code": CURRENCY,
                        "value": formatted_amount
                    }
                }
            ],
            "application_context": {
                "brand_name": "Guardian Pay",
                "return_url": f"{APP_BASE_URL}/paypal/success",
                "cancel_url": f"{APP_BASE_URL}/paypal/cancel",
                "user_action": "PAY_NOW"
            }
        },
        timeout=TIMEOUT
    )

    response.raise_for_status()

    order = response.json()

    order_id = order.get("id")

    if not order_id:
        raise RuntimeError("PayPal did not return an order ID.")

    if order.get("status") != "CREATED":
        raise RuntimeError(
            "PayPal order was not created successfully."
        )

    links = order.get("links", [])

    approval_url = next(
        (
            link.get("href")
            for link in links
            if link.get("rel") in ("approve", "payer-action")
            and str(link.get("href", "")).startswith("https://")
        ),
        None
    )

    if not approval_url:
        raise RuntimeError(
            "PayPal approval URL was not returned."
        )

    return order_id, approval_url


# ==================================================
# VERIFY PAYPAL ORDER BEFORE CAPTURE
# ==================================================

def verify_order(order, expected_amount):

    if not isinstance(order, dict):
        raise RuntimeError("Invalid PayPal order response.")

    if order.get("status") != "APPROVED":
        raise RuntimeError(
            "Buyer has not approved this PayPal order."
        )

    if order.get("intent") != "CAPTURE":
        raise RuntimeError("Unexpected PayPal order intent.")

    purchase_units = order.get("purchase_units", [])

    if len(purchase_units) != 1:
        raise RuntimeError(
            "Unexpected number of PayPal purchase units."
        )

    purchase_unit = purchase_units[0]
    paypal_amount = purchase_unit.get("amount", {})

    if paypal_amount.get("currency_code") != CURRENCY:
        raise RuntimeError("PayPal currency mismatch.")

    expected = Decimal(format_amount(expected_amount))
    actual = Decimal(format_amount(paypal_amount.get("value")))

    if actual != expected:
        raise RuntimeError("PayPal order amount mismatch.")

    return True


# ==================================================
# CAPTURE PAYPAL ORDER
# ==================================================

def capture_order(order_id, expected_amount):

    if not order_id:
        raise ValueError("Missing PayPal order ID.")

    expected_value = format_amount(expected_amount)

    token = get_access_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # STEP 1: Retrieve the actual PayPal order.

    order_response = requests.get(
        f"{BASE_URL}/v2/checkout/orders/{order_id}",
        headers=headers,
        timeout=TIMEOUT
    )

    order_response.raise_for_status()

    order = order_response.json()

    # STEP 2: Verify buyer approval and payment amount.

    verify_order(order, expected_value)

    # STEP 3: Capture only the verified order.

    capture_response = requests.post(
        f"{BASE_URL}/v2/checkout/orders/{order_id}/capture",
        headers={
            **headers,
            "PayPal-Request-Id": f"capture-{order_id}"
        },
        json={},
        timeout=TIMEOUT
    )

    capture_response.raise_for_status()

    result = capture_response.json()

    # STEP 4: Verify capture response.

    if result.get("status") != "COMPLETED":
        raise RuntimeError(
            "PayPal capture was not completed."
        )

    result_units = result.get("purchase_units", [])

    if len(result_units) != 1:
        raise RuntimeError(
            "Invalid PayPal capture purchase units."
        )

    captures = (
        result_units[0]
        .get("payments", {})
        .get("captures", [])
    )

    if not captures:
        raise RuntimeError(
            "PayPal capture details are missing."
        )

    completed_capture = next(
        (
            capture for capture in captures
            if capture.get("status") == "COMPLETED"
        ),
        None
    )

    if not completed_capture:
        raise RuntimeError(
            "No completed PayPal capture found."
        )

    captured_amount = completed_capture.get("amount", {})

    if captured_amount.get("currency_code") != CURRENCY:
        raise RuntimeError("Captured currency mismatch.")

    actual_amount = Decimal(
        format_amount(captured_amount.get("value"))
    )

    if actual_amount != Decimal(expected_value):
        raise RuntimeError(
            "Captured payment amount mismatch."
        )

    return result
