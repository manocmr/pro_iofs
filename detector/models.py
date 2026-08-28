from django.db import models

class SmsAnalysis(models.Model):
    FEEDBACK_CHOICES = [
        ("correct", "Correct"),
        ("false_positive", "Faux positif"),
        ("false_negative", "Faux négatif"),
    ]

    message = models.TextField()
    sender = models.CharField(max_length=32, blank=True, default="")
    risk_score = models.IntegerField()
    label = models.CharField(max_length=20)  # LOW / MEDIUM / HIGH-RISK
    reasons = models.JSONField(default=list)
    user_feedback = models.CharField(
        max_length=20, choices=FEEDBACK_CHOICES, blank=True, default=""
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.label} ({self.risk_score}/100)"


class Transaction(models.Model):
    account_id = models.CharField(max_length=64)
    amount = models.FloatField()
    risk_score = models.IntegerField()
    label = models.CharField(max_length=20)  # LOW-RISK / MEDIUM-RISK / HIGH-RISK
    reasons = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.account_id}: {self.amount} ({self.label})"