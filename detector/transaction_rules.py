import statistics

LARGE_AMOUNT_NO_HISTORY_THRESHOLD = 500_000
VELOCITY_WINDOW_MINUTES = 10
VELOCITY_COUNT_THRESHOLD = 3
ODD_HOURS = set(range(0, 6))  # 00h-05h59, heures les plus rares pour un usage légitime


def label_for_score(score):
    if score >= 70:
        return "HIGH-RISK"
    if score >= 40:
        return "MEDIUM-RISK"
    return "LOW-RISK"


def analyze_transaction(amount, historical_amounts, recent_count, hour):
    """Détecte une transaction anormale par rapport à l'historique d'un compte.

    Fonction pure (pas d'accès DB) : le point d'appel fournit l'historique des
    montants du compte, le nombre de transactions récentes (vélocité) et
    l'heure courante, pour rester testable indépendamment de Django.
    """
    score = 0
    reasons = []

    if len(historical_amounts) >= 3:
        mean = statistics.mean(historical_amounts)
        stdev = statistics.pstdev(historical_amounts)
        if stdev > 0:
            z_score = (amount - mean) / stdev
            if z_score >= 3:
                score += 45
                reasons.append(
                    f"Montant très inhabituel par rapport à l'historique du compte (z-score={z_score:.1f})"
                )
            elif z_score >= 2:
                score += 25
                reasons.append(
                    f"Montant nettement supérieur à la moyenne du compte (z-score={z_score:.1f})"
                )
    elif amount >= LARGE_AMOUNT_NO_HISTORY_THRESHOLD:
        score += 20
        reasons.append("Montant élevé pour un compte sans historique de référence")

    if recent_count >= VELOCITY_COUNT_THRESHOLD:
        score += 30
        reasons.append(
            f"Vélocité anormale : {recent_count} transactions dans les {VELOCITY_WINDOW_MINUTES} dernières minutes"
        )

    if hour in ODD_HOURS:
        score += 15
        reasons.append("Transaction effectuée à une heure inhabituelle (00h-06h)")

    score = min(score, 100)
    return {
        "risk_score": score,
        "label": label_for_score(score),
        "reasons": reasons,
    }
