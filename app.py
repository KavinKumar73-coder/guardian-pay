import os
import time
import uuid
import secrets
import hmac
import threading
from decimal import Decimal, InvalidOperation

from flask import (
    Flask,
    request,
    render_template,
    redirect,
    url_for,
    session,
    jsonify
)
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables before importing application modules.
load_dotenv()

from ai_scorer import score_payment_ai
from rules import make_decision
from paypal import create_order, capture_order


# ==================================================
# APPLICATION CONFIGURATION
# ==================================================

# On Render, configure environment values through the service
# Environment settings; the local .env file is not deployed.

# Flask automatically looks for:
#   templates/  -> HTML (Jinja2) templates
#   static/     -> CSS, JavaScript, images
# Both folders must sit next to this file.
app = Flask(__name__)

APP_BASE_URL = (
    os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")
    .strip()
    .rstrip("/")
)

IS_RENDER = os.getenv("RENDER", "").lower() == "true"
IS_PRODUCTION = IS_RENDER or APP_BASE_URL.startswith("https://")

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")

# A public deployment must use a stable signing key.
if IS_PRODUCTION and not FLASK_SECRET_KEY:
    raise RuntimeError(
        "FLASK_SECRET_KEY must be configured in the deployment environment."
    )

if IS_RENDER and not APP_BASE_URL.startswith("https://"):
    raise RuntimeError(
        "APP_BASE_URL must be the public HTTPS URL of the Render service."
    )

app.secret_key = FLASK_SECRET_KEY or secrets.token_hex(32)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_PRODUCTION,
    PREFERRED_URL_SCHEME="https" if IS_PRODUCTION else "http",
    MAX_CONTENT_LENGTH=16 * 1024
)

# Render terminates HTTPS at its reverse proxy. Trust the forwarded
# scheme/host so external URLs use the public HTTPS address.
if IS_PRODUCTION:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1
    )

GUARDIAN_LINK_EXPIRY = 600
MAX_PAYMENT_AMOUNT = Decimal("100000.00")

# Demo storage: records disappear when the server restarts.
payments = {}

# Protect transaction state changes against concurrent requests.
payment_lock = threading.RLock()


# ==================================================
# SECURITY HELPERS
# ==================================================

def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)

    return session["csrf_token"]


def validate_csrf():
    submitted = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")

    return bool(
        submitted
        and expected
        and hmac.compare_digest(submitted, expected)
    )


def find_payment(payment_id):
    with payment_lock:
        return payments.get(payment_id)


def find_guardian_payment(token):
    if not token:
        return None

    with payment_lock:
        for payment in payments.values():
            stored_token = payment.get("guardian_token")

            if (
                stored_token
                and hmac.compare_digest(stored_token, token)
            ):
                return payment

    return None


def validate_amount(raw_amount):
    try:
        amount = Decimal(raw_amount)

        if not amount.is_finite():
            return None

        if amount <= 0 or amount > MAX_PAYMENT_AMOUNT:
            return None

        if amount != amount.quantize(Decimal("0.01")):

            return None

        return amount.quantize(Decimal("0.01"))

    except (InvalidOperation, ValueError, TypeError):
        return None


def valid_risk_response(risk):
    if not isinstance(risk, dict):
        return False

    try:
        score = int(risk.get("score"))
    except (ValueError, TypeError):
        return False

    return (
        0 <= score <= 100
        and isinstance(risk.get("verdict"), str)
        and isinstance(risk.get("reasons", []), list)
        and isinstance(risk.get("advice", ""), str)
    )


# ==================================================
# MESSAGE + ERROR PAGES
# ==================================================

# Every message that used to be returned as plain text or
# as inline HTML now goes through templates/message.html.
# The wording and the HTTP status codes are unchanged.

ERROR_TITLES = {
    400: "Request not accepted",
    403: "Not allowed",
    404: "Not found",
    409: "Not available",
    410: "Link no longer valid",
    502: "PayPal problem",
    503: "Service unavailable",
}


def render_message(title, message, kind="neutral",
                   status=200, details=None):
    return (
        render_template(
            "message.html",
            title=title,
            message=message,
            kind=kind,
            details=details
        ),
        status
    )


def error_page(message, status):
    return render_message(
        ERROR_TITLES.get(status, "Something went wrong"),
        message,
        kind="error",
        status=status
    )


# ==================================================
# PAYPAL CHECKOUT
# ==================================================

def create_paypal_checkout(payment_id, allowed_statuses):
    """
    Creates a PayPal order only after the payment
    has passed the required application checks.

    Buyer must still approve payment on PayPal.
    """

    with payment_lock:
        payment = payments.get(payment_id)

        if not payment:
            return error_page("Payment not found.", 404)

        if payment["status"] not in allowed_statuses:
            return error_page("Payment is not eligible for checkout.", 409)

        # Reserve transaction before external API call.
        payment["status"] = "checkout_creating"

    try:
        order_id, approval_url = create_order(
            float(payment["amount"])
        )

        if not order_id or not approval_url:
            raise ValueError("PayPal returned incomplete order details.")

        # Require HTTPS for the external approval link.
        if not str(approval_url).startswith("https://"):
            raise ValueError("Invalid PayPal approval URL.")

        with payment_lock:
            payment["paypal_order_id"] = str(order_id)
            payment["status"] = "awaiting_buyer_approval"

        return redirect(approval_url)

    except Exception as error:
        with payment_lock:
            payment["status"] = "checkout_failed"

        app.logger.exception("PayPal checkout creation failed: %s", error)

        return error_page("Unable to create PayPal checkout.", 502)


# ==================================================
# RESPONSE SECURITY HEADERS
# ==================================================

@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Referrer-Policy",
        "strict-origin-when-cross-origin"
    )
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()"
    )

    if IS_PRODUCTION:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains"
        )

    return response


# ==================================================
# HEALTH CHECK
# ==================================================

@app.route("/health")
def health():
    return jsonify(status="ok"), 200


# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
def home():
    return render_template(
        "index.html",
        csrf_token=get_csrf_token()
    )


# ==================================================
# GEMINI AI + FAMILY RULES
# ==================================================

@app.route("/score", methods=["POST"])
def score():

    if not validate_csrf():
        return error_page(
            "Invalid or expired form token. Reload and try again.",
            400
        )

    payee = request.form.get("payee", "").strip()
    message = request.form.get("message", "").strip()

    if not payee or len(payee) > 100:
        return error_page("Enter a valid payee name.", 400)

    if len(message) > 1000:
        return error_page("Payment message is too long.", 400)

    amount = validate_amount(request.form.get("amount", ""))

    if amount is None:
        return error_page(
            "Enter a valid amount between $0.01 and $100,000.",
            400
        )

    # STEP 1: Gemini analysis
    try:
        risk = score_payment_ai(
            payee,
            float(amount),
            message
        )

        if not valid_risk_response(risk):
            raise ValueError("Invalid Gemini response format.")

    except Exception:
        app.logger.exception("Gemini analysis failed.")

        return error_page(
            "Gemini analysis is unavailable or invalid. "
            "No payment was processed. Please try again.",
            503
        )

    # STEP 2: Family rules
    try:
        decision = make_decision(
            payee,
            float(amount),
            risk
        )
        if not isinstance(decision, dict):
            raise ValueError("Invalid decision response.")

        if decision.get("decision") not in (
            "AUTO_PAY",
            "HOLD",
            "BLOCK"
        ):
            raise ValueError("Unknown payment decision.")

    except Exception:
        app.logger.exception("Family rule evaluation failed.")

        return error_page(
            "Payment decision could not be verified. "
            "No payment was processed.",
            503
        )

    # STEP 3: Store payment
    payment_id = uuid.uuid4().hex

    payment = {
        "id": payment_id,
        "payee": payee,
        "amount": amount,
        "message": message,
        "risk": risk,
        "decision": decision,
        "status": "analyzed",
        "created_at": time.time(),
        "guardian_token": None,
        "guardian_token_used": False,
        "paypal_order_id": None
    }

    with payment_lock:
        payments[payment_id] = payment

    # STEP 4: Generate next action
    checkout_csrf = get_csrf_token()

    guardian_url = None

    if decision["decision"] == "HOLD":

        guardian_token = secrets.token_urlsafe(32)

        with payment_lock:
            payment["guardian_token"] = guardian_token

        guardian_url = url_for(
            "guardian_review",
            token=guardian_token,
            _external=True
        )

    # STEP 5: Display analysis
    return render_template(
        "result.html",
        risk=risk,
        decision=decision,
        payee=payee,
        amount=amount,
        payment_id=payment_id,
        guardian_url=guardian_url,
        csrf_token=checkout_csrf
    )


# ==================================================
# AUTO PAY CHECKOUT
# ==================================================

@app.route("/checkout/<payment_id>", methods=["POST"])
def checkout(payment_id):

    if not validate_csrf():
        return error_page("Invalid form token.", 400)

    payment = find_payment(payment_id)

    if not payment:
        return error_page("Payment request not found.", 404)

    if payment["decision"]["decision"] != "AUTO_PAY":
        return error_page(
            "Payment is not eligible for direct checkout.",
            403
        )

    return create_paypal_checkout(
        payment_id,
        allowed_statuses={"analyzed"}
    )


# ==================================================
# GUARDIAN APPROVAL / DENIAL
# ==================================================

@app.route("/guardian/<token>", methods=["GET", "POST"])
def guardian_review(token):

    payment = find_guardian_payment(token)

    if not payment:
        return error_page("Invalid guardian link.", 404)

    with payment_lock:

        if payment["guardian_token_used"]:
            return error_page("Guardian link already used.", 410)

        if time.time() - payment["created_at"] > GUARDIAN_LINK_EXPIRY:
            payment["guardian_token_used"] = True
            payment["guardian_token"] = None
            return error_page("Guardian link expired.", 410)

        if payment["status"] != "analyzed":
            return error_page(
                "Payment is no longer awaiting review.",
                409
            )

    if request.method == "GET":

        return render_template(
            "guardian.html",
            payment=payment,
            csrf_token=get_csrf_token()
        )

    if not validate_csrf():
        return error_page("Invalid form token.", 400)

    action = request.form.get("action")

    if action not in ("approve", "deny"):
        return error_page("Invalid action.", 400)

    # Atomically consume the guardian link.
    with payment_lock:

        if payment["guardian_token_used"]:
            return error_page("Guardian link already used.", 410)

        if payment["status"] != "analyzed":
            return error_page(
                "Payment is no longer awaiting review.",
                409
            )

        if time.time() - payment["created_at"] > GUARDIAN_LINK_EXPIRY:
            payment["guardian_token_used"] = True
            payment["guardian_token"] = None
            return error_page("Guardian link expired.", 410)

        payment["guardian_token_used"] = True
        payment["guardian_token"] = None

        if action == "deny":
            payment["status"] = "denied"

        else:
            payment["status"] = "guardian_approved"

    if action == "deny":

        return render_message(
            "Payment denied",
            "No PayPal order was created."
        )

    return create_paypal_checkout(
        payment["id"],
        allowed_statuses={"guardian_approved"}
    )


# ==================================================
# PAYPAL SUCCESS + CAPTURE
# ==================================================

@app.route("/paypal/success")
def paypal_success():

    order_id = request.args.get("token", "").strip()

    if not order_id:
        return error_page("Missing PayPal order ID.", 400)

    # Find the exact order and reserve it for capture.
    with payment_lock:

        payment = next(
            (
                p for p in payments.values()
                if p["paypal_order_id"] == order_id
            ),
            None
        )

        if not payment:
            return error_page("Unknown PayPal order. Capture refused.", 404)

        if payment["status"] != "awaiting_buyer_approval":
            return error_page("This order cannot be captured again.", 409)

        payment["status"] = "capturing"

    try:

        result = capture_order(
            order_id,
            float(payment["amount"])
        )

        if not isinstance(result, dict):
            raise ValueError("Invalid PayPal capture response.")

        if result.get("status") != "COMPLETED":

            with payment_lock:
                payment["status"] = "capture_failed"

            return error_page(
                "PayPal did not confirm payment completion.",
                502
            )

        with payment_lock:
            payment["status"] = "completed"

        return render_message(
            "Payment completed",
            "PayPal confirmed the payment.",
            kind="success",
            details=[
                ("Payee", payment["payee"]),
                ("Amount", f"${payment['amount']:.2f}"),
                ("PayPal status", result.get("status")),
                ("Order ID", order_id),
            ]
        )

    except Exception:

        # Do not automatically retry an uncertain capture.
        # Check PayPal Sandbox before attempting recovery.
        with payment_lock:
            payment["status"] = "capture_uncertain"

        app.logger.exception("PayPal capture failed or became uncertain.")

        return error_page(
            "Payment capture could not be confirmed. "
            "Check PayPal Sandbox before retrying. "
            "Do not submit another payment.",
            502
        )


# ==================================================
# PAYPAL CANCEL
# ==================================================

@app.route("/paypal/cancel")
def paypal_cancel():

    order_id = request.args.get("token", "").strip()

    if not order_id:
        return error_page("Missing PayPal order ID.", 400)

    with payment_lock:

        payment = next(
            (
                p for p in payments.values()
                if p["paypal_order_id"] == order_id
            ),
            None
        )

        if not payment:
            return error_page("Unknown PayPal order.", 404)

        if payment["status"] != "awaiting_buyer_approval":
            return error_page(
                "This payment can no longer be cancelled here.",
                409
            )

        payment["status"] = "cancelled"

    return render_message(
        "Payment cancelled",
        "No capture was performed by Guardian Pay."
    )


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(
        debug=False,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        threaded=True
    )
