from rest_framework import serializers
from .models import SmsAnalysis, Transaction

class SmsAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsAnalysis
        fields = "__all__"


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = "__all__"
