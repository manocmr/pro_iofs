from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .fraud_rules import analyze_sms, label_for_score
from .ml.evaluate import evaluate as evaluate_ml_model
from .models import SmsAnalysis, Transaction
from .permissions import HasAPIKey
from .serializers import SmsAnalysisSerializer, TransactionSerializer
from .transaction_rules import VELOCITY_WINDOW_MINUTES, analyze_transaction


def demo_view(request):
    return render(request, "detector/demo.html", {"api_key": settings.API_KEY})

REPEAT_OFFENDER_BONUS_PER_HIT = 10
REPEAT_OFFENDER_MAX_BONUS = 20


def _run_analysis(message, sender):
    result = analyze_sms(message)

    sender = (sender or "").strip()
    if sender:
        repeat_count = SmsAnalysis.objects.filter(
            sender=sender, label__in=["MEDIUM-RISK", "HIGH-RISK FRAUD"]
        ).count()
        if repeat_count > 0:
            bonus = min(repeat_count * REPEAT_OFFENDER_BONUS_PER_HIT, REPEAT_OFFENDER_MAX_BONUS)
            result["risk_score"] = min(result["risk_score"] + bonus, 100)
            result["label"] = label_for_score(result["risk_score"])
            result["reasons"].append(
                f"Numéro déjà signalé {repeat_count} fois comme suspect"
            )

    return result, sender


@api_view(["POST"])
@permission_classes([HasAPIKey])
def analyze_view(request):
    message = request.data.get("message", "")
    sender = request.data.get("sender", "")

    if not message:
        return Response({"error": "Le champ 'message' est requis."}, status=400)

    result, sender = _run_analysis(message, sender)

    record = SmsAnalysis.objects.create(
        message=message,
        sender=sender,
        risk_score=result["risk_score"],
        label=result["label"],
        reasons=result["reasons"],
    )

    return Response(SmsAnalysisSerializer(record).data)


@api_view(["POST"])
@permission_classes([HasAPIKey])
def webhook_view(request):
    """Endpoint générique pour brancher une passerelle SMS (Twilio, Africa's Talking, ...).

    Payload attendu (adapter le mapping du fournisseur en amont si besoin) :
        {"from": "+225xxxxxxxxx", "text": "contenu du sms"}
    """
    message = request.data.get("text", "") or request.data.get("message", "")
    sender = request.data.get("from", "") or request.data.get("sender", "")

    if not message:
        return Response({"error": "Le champ 'text' est requis."}, status=400)

    result, sender = _run_analysis(message, sender)

    record = SmsAnalysis.objects.create(
        message=message,
        sender=sender,
        risk_score=result["risk_score"],
        label=result["label"],
        reasons=result["reasons"],
    )

    return Response(SmsAnalysisSerializer(record).data, status=201)


@api_view(["POST"])
@permission_classes([HasAPIKey])
def feedback_view(request, pk):
    try:
        record = SmsAnalysis.objects.get(pk=pk)
    except SmsAnalysis.DoesNotExist:
        return Response({"error": "Analyse introuvable."}, status=404)

    feedback = request.data.get("feedback", "")
    valid_choices = dict(SmsAnalysis.FEEDBACK_CHOICES)
    if feedback not in valid_choices:
        return Response(
            {"error": f"'feedback' doit être l'une de : {list(valid_choices)}"},
            status=400,
        )

    record.user_feedback = feedback
    record.save(update_fields=["user_feedback"])

    return Response(SmsAnalysisSerializer(record).data)


@api_view(["GET"])
@permission_classes([HasAPIKey])
def stats_view(request):
    total = SmsAnalysis.objects.count()

    by_label = {
        row["label"]: row["count"]
        for row in SmsAnalysis.objects.values("label").annotate(count=Count("id"))
    }

    reasons_counter = Counter()
    for reasons in SmsAnalysis.objects.order_by("-created_at")[:500].values_list(
        "reasons", flat=True
    ):
        reasons_counter.update(reasons)

    repeat_senders = (
        SmsAnalysis.objects.exclude(sender="")
        .values("sender")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
        .order_by("-count")[:10]
    )

    return Response(
        {
            "total_analyses": total,
            "by_label": by_label,
            "top_reasons": [
                {"reason": reason, "count": count}
                for reason, count in reasons_counter.most_common(5)
            ],
            "repeat_senders": list(repeat_senders),
        }
    )


@api_view(["POST"])
@permission_classes([HasAPIKey])
def analyze_transaction_view(request):
    account_id = request.data.get("account_id", "")
    amount = request.data.get("amount")

    if not account_id or amount is None:
        return Response(
            {"error": "Les champs 'account_id' et 'amount' sont requis."}, status=400
        )

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return Response({"error": "'amount' doit être un nombre."}, status=400)

    history_qs = Transaction.objects.filter(account_id=account_id)
    historical_amounts = list(history_qs.values_list("amount", flat=True))

    window_start = timezone.now() - timedelta(minutes=VELOCITY_WINDOW_MINUTES)
    recent_count = history_qs.filter(created_at__gte=window_start).count()

    result = analyze_transaction(
        amount=amount,
        historical_amounts=historical_amounts,
        recent_count=recent_count,
        hour=timezone.now().hour,
    )

    record = Transaction.objects.create(
        account_id=account_id,
        amount=amount,
        risk_score=result["risk_score"],
        label=result["label"],
        reasons=result["reasons"],
    )

    return Response(TransactionSerializer(record).data, status=201)


@api_view(["GET"])
@permission_classes([HasAPIKey])
def ml_evaluation_view(request):
    """Métriques de validation croisée du classifieur ML (accuracy, precision, recall, F1)."""
    return Response(evaluate_ml_model())
