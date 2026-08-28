from rest_framework.decorators import api_view
from rest_framework.response import Response
from .fraud_rules import analyze_sms
from .models import SmsAnalysis
from .serializers import SmsAnalysisSerializer

@api_view(["POST"])
def analyze_view(request):
    message = request.data.get("message", "")

    if not message:
        return Response({"error": "Le champ 'message' est requis."}, status=400)

    result = analyze_sms(message)

    record = SmsAnalysis.objects.create(
        message=message,
        risk_score=result["risk_score"],
        label=result["label"],
        reasons=result["reasons"],
    )

    return Response(SmsAnalysisSerializer(record).data)