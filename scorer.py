
def score_payment(payee, amount, message):
    score = 0
    reasons = []
    message_lower = message.lower()

    suspicious_words = [
        "urgent",
        "gift card",
        "verify account",
        "password",
        "otp",
        "prize",
        "crypto",
        "immediately",
        "threat",
        "suspended"
    ]

    for word in suspicious_words:
        if word in message_lower:
            score += 15
            reasons.append(f"Suspicious message contains: {word}")

    if amount >= 500:
        score += 20
        reasons.append("Unusually large payment amount")

    if amount >= 1000:
        score += 15
        reasons.append("Payment exceeds $1,000")

    if not payee.strip():
        score += 30
        reasons.append("Payee identity is missing")

    score = min(score, 100)

    if score >= 90:
        verdict = "BLOCK"
        advice = "Strong scam indicators. Do not proceed."
    elif score >= 60:
        verdict = "HOLD"
        advice = "Guardian approval required."
    else:
        verdict = "REVIEW"
        advice = "Continue checking family rules before payment."

    if not reasons:
        reasons.append("No suspicious message signals detected")

    return {
        "score": score,
        "verdict": verdict,
        "reasons": reasons,
        "advice": advice
    }


if __name__ == "__main__":
    result = score_payment(
        "Unknown Seller",
        750,
        "Urgent! Verify account immediately to receive your prize."
    )

    print(result)
