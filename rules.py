
# Guardian Pay - Family Decision Engine

TRUSTED_PAYEES = {
    "green garden landscaping"
}

SPENDING_LIMIT = 100.00

BLOCK_THRESHOLD = 90
HOLD_THRESHOLD = 60


def make_decision(payee, amount, risk):

    payee_normalized = payee.strip().lower()

    score = risk["score"]

    reasons = []

    # 1. Critical scam risk: always block
    if score >= BLOCK_THRESHOLD:
        return {
            "decision": "BLOCK",
            "reasons": [
                "Critical scam risk detected."
            ],
            "explanation": (
                "Strong scam indicators detected. "
                "Payment blocked."
            )
        }

    # 2. Verify merchant identity
    trusted = payee_normalized in TRUSTED_PAYEES

    if not trusted:
        reasons.append(
            "Merchant is not on the family's verified list."
        )

    # 3. Check family spending limit
    if amount > SPENDING_LIMIT:
        reasons.append(
            f"Payment exceeds the family limit of "
            f"${SPENDING_LIMIT:.2f}."
        )

    # 4. Check AI risk score
    if score >= HOLD_THRESHOLD:
        reasons.append(
            "Payment risk requires guardian review."
        )

    # 5. Any failed condition requires HOLD
    if reasons:
        return {
            "decision": "HOLD",
            "reasons": reasons,
            "explanation": (
                "Payment held until guardian approval."
            )
        }

    # 6. All conditions satisfied
    return {
        "decision": "AUTO_PAY",
        "reasons": [
            "Merchant identity verified.",
            "Within family spending limit.",
            "AI risk score is below the review threshold."
        ],
        "explanation": (
            "Eligible for the normal PayPal checkout flow. "
            "Payer authorization is still required."
        )
    }
