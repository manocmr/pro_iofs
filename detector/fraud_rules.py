import re
import unicodedata

from .ml.classifier import predict_fraud_probability
from .url_signals import analyze_urls

KEYWORDS = {
    "bloqué": 25,
    "blocked": 25,
    "réactiver": 20,
    "reactivate": 20,
    "dial": 20,
    "composez": 20,
    "urgent": 15,
    "immédiatement": 15,
    "code pin": 30,
    "code secret": 30,
    "compte mobile money": 20,
}

# Motifs regex pour des formes suspectes qu'un simple mot-clé ne peut pas capturer
# (ex: codes USSD réels comme *123# ou *555*1#).
PATTERNS = {
    r"\*\d+(?:\*\d+)*#": ("Contient un code USSD suspect", 30),
}


def _strip_accents(text):
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _normalize(text):
    text = _strip_accents(text.lower())
    return re.sub(r"\s+", " ", text).strip()


def label_for_score(score):
    if score >= 70:
        return "HIGH-RISK FRAUD"
    if score >= 40:
        return "MEDIUM-RISK"
    return "LOW-RISK"


def analyze_sms(text):
    normalized = _normalize(text)
    despaced = normalized.replace(" ", "")

    rule_score = 0
    reasons = []

    for keyword, points in KEYWORDS.items():
        norm_keyword = _normalize(keyword)
        despaced_keyword = norm_keyword.replace(" ", "")
        if norm_keyword in normalized or (despaced_keyword and despaced_keyword in despaced):
            rule_score += points
            reasons.append(f"Contient le mot suspect : '{keyword}'")

    for pattern, (reason, points) in PATTERNS.items():
        if re.search(pattern, normalized):
            rule_score += points
            reasons.append(reason)

    url_score, url_reasons = analyze_urls(text)
    reasons.extend(url_reasons)

    deterministic_score = min(rule_score + url_score, 100)

    ml_score = predict_fraud_probability(text)
    if ml_score >= 50:
        reasons.append(f"Le modèle ML estime une probabilité de fraude de {ml_score}%")

    # On pondère davantage les règles/heuristiques (déterministes, explicables)
    # que le modèle ML (entraîné sur un petit jeu d'exemples synthétique pour l'instant).
    score = round(0.6 * deterministic_score + 0.4 * ml_score)
    score = min(score, 100)

    return {
        "risk_score": score,
        "label": label_for_score(score),
        "reasons": reasons,
    }
