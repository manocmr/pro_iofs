from rest_framework import serializers
from .models import SmsAnalysis

class SmsAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmsAnalysis
        fields = "__all__"