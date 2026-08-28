from django.urls import path
from .views import (
    analyze_transaction_view,
    analyze_view,
    feedback_view,
    ml_evaluation_view,
    stats_view,
    webhook_view,
)

urlpatterns = [
    path("analyze/", analyze_view, name="analyze_sms"),
    path("webhook/", webhook_view, name="sms_webhook"),
    path("feedback/<int:pk>/", feedback_view, name="analysis_feedback"),
    path("stats/", stats_view, name="analysis_stats"),
    path("transactions/analyze/", analyze_transaction_view, name="analyze_transaction"),
    path("ml/evaluation/", ml_evaluation_view, name="ml_evaluation"),
]
