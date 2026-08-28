KEYWORDS = {
    "bloqué": 25,
    "blocked": 25,
    "réactiver": 20,
    "reactivate": 20,
    "dial": 20,
    "composez": 20,
    "*xxx#": 30,
    "urgent": 15,
    "immédiatement": 15,
    "code pin": 30,
    "code secret": 30,
    "compte mobile money": 20,
}

def analyze_sms(text):
    text_lower = text.lower()
    score = 0
    reasons = []

    for keyword, points in KEYWORDS.items():
        if keyword in text_lower:
            score += points
            reasons.append(f"Contient le mot suspect : '{keyword}'")

    score = min(score, 100)

    if score >= 70:
        label = "HIGH-RISK FRAUD"
    elif score >= 40:
        label = "MEDIUM-RISK"
    else:
        label = "LOW-RISK"

    return {
        "risk_score": score,
        "label": label,
        "reasons": reasons,
    }