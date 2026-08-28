from django.test import override_settings
from rest_framework.test import APITestCase

from .fraud_rules import analyze_sms
from .models import SmsAnalysis, Transaction
from .transaction_rules import analyze_transaction
from .url_signals import analyze_urls

TEST_API_KEY = "test-key"


@override_settings(API_KEY=TEST_API_KEY)
class AuthenticatedAPITestCase(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_KEY=TEST_API_KEY)


class FraudRulesTests(APITestCase):
    def test_legitimate_message_is_low_risk(self):
        result = analyze_sms("Salut, on se voit a 18h pour le foot ?")
        self.assertEqual(result["label"], "LOW-RISK")
        self.assertLess(result["risk_score"], 40)

    def test_keyword_message_is_flagged(self):
        result = analyze_sms(
            "Votre compte est bloqué, composez *123# immédiatement pour le réactiver"
        )
        self.assertIn(result["label"], ["MEDIUM-RISK", "HIGH-RISK FRAUD"])
        self.assertGreater(result["risk_score"], 0)
        self.assertTrue(any("USSD" in r for r in result["reasons"]))

    def test_accent_stripped_evasion_is_still_caught(self):
        # Meme mot-cle sans accents : "bloque" doit matcher "bloqué".
        result = analyze_sms("Votre compte mobile money est bloque")
        self.assertTrue(any("bloqué" in r for r in result["reasons"]))

    def test_letter_spaced_evasion_is_caught(self):
        result = analyze_sms("entrez votre c o d e  p i n immediatement")
        self.assertTrue(any("code pin" in r for r in result["reasons"]))

    def test_shortened_url_adds_risk(self):
        result = analyze_sms("Cliquez ici http://bit.ly/verify pour reactiver votre compte")
        self.assertTrue(any("bit.ly" in r for r in result["reasons"]))

    def test_score_never_exceeds_100(self):
        text = " ".join(["bloqué urgent code pin code secret *999#"] * 5)
        result = analyze_sms(text)
        self.assertLessEqual(result["risk_score"], 100)


class UrlSignalsTests(APITestCase):
    def test_raw_ip_url_is_flagged(self):
        score, reasons = analyze_urls("Cliquez sur http://192.168.1.1/login")
        self.assertGreater(score, 0)
        self.assertTrue(any("adresse IP" in r for r in reasons))

    def test_no_url_returns_zero(self):
        score, reasons = analyze_urls("Pas de lien ici")
        self.assertEqual(score, 0)
        self.assertEqual(reasons, [])


class TransactionRulesTests(APITestCase):
    def test_no_history_small_amount_is_low_risk(self):
        result = analyze_transaction(
            amount=5000, historical_amounts=[], recent_count=0, hour=14
        )
        self.assertEqual(result["label"], "LOW-RISK")

    def test_large_amount_without_history_is_flagged(self):
        result = analyze_transaction(
            amount=800_000, historical_amounts=[], recent_count=0, hour=14
        )
        self.assertGreater(result["risk_score"], 0)
        self.assertTrue(any("sans historique" in r for r in result["reasons"]))

    def test_outlier_amount_vs_history_is_flagged(self):
        history = [10_000, 12_000, 9_000, 11_000, 10_500]
        result = analyze_transaction(
            amount=200_000, historical_amounts=history, recent_count=0, hour=14
        )
        self.assertGreaterEqual(result["risk_score"], 40)
        self.assertTrue(any("z-score" in r for r in result["reasons"]))

    def test_high_velocity_is_flagged(self):
        result = analyze_transaction(
            amount=5000, historical_amounts=[], recent_count=4, hour=14
        )
        self.assertTrue(any("Vélocité" in r for r in result["reasons"]))

    def test_odd_hour_is_flagged(self):
        result = analyze_transaction(
            amount=5000, historical_amounts=[], recent_count=0, hour=3
        )
        self.assertTrue(any("heure inhabituelle" in r for r in result["reasons"]))


class AuthenticationTests(APITestCase):
    def test_missing_api_key_is_rejected(self):
        response = self.client.post(
            "/api/analyze/", {"message": "test"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_wrong_api_key_is_rejected(self):
        self.client.credentials(HTTP_X_API_KEY="wrong-key")
        response = self.client.post(
            "/api/analyze/", {"message": "test"}, format="json"
        )
        self.assertEqual(response.status_code, 403)


class AnalyzeEndpointTests(AuthenticatedAPITestCase):
    def test_missing_message_returns_400(self):
        response = self.client.post("/api/analyze/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_valid_message_creates_record(self):
        response = self.client.post(
            "/api/analyze/", {"message": "Bonjour, tu es dispo ce soir ?"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SmsAnalysis.objects.count(), 1)
        self.assertIn("risk_score", response.data)

    def test_repeat_sender_increases_score(self):
        sender = "+225000000"
        # Deux signalements suspects prealables pour ce numero.
        for _ in range(2):
            self.client.post(
                "/api/analyze/",
                {"message": "Votre compte est bloqué, code pin requis", "sender": sender},
                format="json",
            )

        response = self.client.post(
            "/api/analyze/", {"message": "Bonjour", "sender": sender}, format="json"
        )
        self.assertTrue(
            any("déjà signalé" in r for r in response.data["reasons"])
        )


class WebhookEndpointTests(AuthenticatedAPITestCase):
    def test_webhook_accepts_gateway_payload(self):
        response = self.client.post(
            "/api/webhook/",
            {"from": "+225123456", "text": "Votre compte est bloqué"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SmsAnalysis.objects.count(), 1)
        self.assertEqual(SmsAnalysis.objects.first().sender, "+225123456")

    def test_webhook_missing_text_returns_400(self):
        response = self.client.post("/api/webhook/", {"from": "+225123456"}, format="json")
        self.assertEqual(response.status_code, 400)


class FeedbackEndpointTests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.record = SmsAnalysis.objects.create(
            message="test", risk_score=80, label="HIGH-RISK FRAUD", reasons=[]
        )

    def test_valid_feedback_updates_record(self):
        response = self.client.post(
            f"/api/feedback/{self.record.pk}/",
            {"feedback": "false_positive"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.user_feedback, "false_positive")

    def test_invalid_feedback_rejected(self):
        response = self.client.post(
            f"/api/feedback/{self.record.pk}/", {"feedback": "nonsense"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_record_returns_404(self):
        response = self.client.post(
            "/api/feedback/9999/", {"feedback": "correct"}, format="json"
        )
        self.assertEqual(response.status_code, 404)


class StatsEndpointTests(AuthenticatedAPITestCase):
    def test_stats_reflects_created_records(self):
        SmsAnalysis.objects.create(
            message="a", risk_score=10, label="LOW-RISK", reasons=[]
        )
        SmsAnalysis.objects.create(
            message="b", risk_score=90, label="HIGH-RISK FRAUD", reasons=["x"]
        )

        response = self.client.get("/api/stats/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_analyses"], 2)
        self.assertEqual(response.data["by_label"]["LOW-RISK"], 1)
        self.assertEqual(response.data["by_label"]["HIGH-RISK FRAUD"], 1)


class TransactionEndpointTests(AuthenticatedAPITestCase):
    def test_missing_fields_returns_400(self):
        response = self.client.post("/api/transactions/analyze/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_valid_transaction_creates_record(self):
        response = self.client.post(
            "/api/transactions/analyze/",
            {"account_id": "acc-1", "amount": 5000},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_outlier_amount_flagged_against_account_history(self):
        for amount in [10_000, 11_000, 9_500, 10_200]:
            self.client.post(
                "/api/transactions/analyze/",
                {"account_id": "acc-2", "amount": amount},
                format="json",
            )

        response = self.client.post(
            "/api/transactions/analyze/",
            {"account_id": "acc-2", "amount": 500_000},
            format="json",
        )
        self.assertGreaterEqual(response.data["risk_score"], 40)


class MlEvaluationEndpointTests(AuthenticatedAPITestCase):
    def test_returns_classification_metrics(self):
        response = self.client.get("/api/ml/evaluation/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("accuracy", response.data["report"])
        self.assertGreater(response.data["n_samples"], 0)
