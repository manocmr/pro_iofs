from django.db import models

class SmsAnalysis(models.Model):
    message = models.TextField()
    risk_score = models.IntegerField()
    label = models.CharField(max_length=20)  # LOW / MEDIUM / HIGH-RISK
    reasons = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.label} ({self.risk_score}/100)"