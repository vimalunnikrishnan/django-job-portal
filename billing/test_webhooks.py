import json
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from billing.models import (
    BillingHistory,
    PaymentTransaction,
    ProcessedWebhookEvent,
    SubscriptionPlan,
    UserSubscription,
)


class RazorpayWebhookTest(APITestCase):
    webhook_url = "/api/billing/razorpay/webhook/"

    def setUp(self):
        self.employer = User.objects.create_user(
            username="webhookemployer",
            email="webhookemployer@example.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.plan = SubscriptionPlan.objects.create(
            name="PRO",
            description="Pro subscription for webhook tests.",
            price=Decimal("999.00"),
            duration_days=30,
            job_post_limit=None,
            includes_analytics=False,
        )

        self.subscription = UserSubscription.objects.create(
            user=self.employer,
            plan=self.plan,
            status="PENDING",
        )

    def create_payment(self):
        return PaymentTransaction.objects.create(
            subscription=self.subscription,
            amount=Decimal("999.00"),
            currency="INR",
            status="PENDING",
            provider="Razorpay",
            provider_order_id="order_test_123",
        )

    def send_webhook(self, event_type, entity, event_id):
        payload = json.dumps({
            "event": event_type,
            "payload": {
                "payment": {
                    "entity": entity if event_type.startswith("payment.")
                    else {},
                },
                "refund": {
                    "entity": entity if event_type == "refund.processed"
                    else {},
                },
            },
        }).encode("utf-8")

        return self.client.post(
            self.webhook_url,
            data=payload,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE="test-signature",
            HTTP_X_RAZORPAY_EVENT_ID=event_id,
        )

    @patch("billing.views.verify_webhook_signature", return_value=False)
    def test_invalid_signature_is_rejected(self, mock_verify):
        response = self.client.post(
            self.webhook_url,
            data=b'{"event":"payment.captured"}',
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE="invalid-signature",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertFalse(response.data["success"])
        mock_verify.assert_called_once()

    @patch("billing.views.verify_webhook_signature", return_value=True)
    def test_payment_captured_activates_subscription(self, mock_verify):
        payment = self.create_payment()

        response = self.send_webhook(
            "payment.captured",
            {
                "id": "pay_test_123",
                "order_id": payment.provider_order_id,
                "amount": 99900,
                "currency": "INR",
            },
            "event_capture_001",
        )

        payment.refresh_from_db()
        self.subscription.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payment.status, "SUCCESS")
        self.assertEqual(payment.provider_transaction_id, "pay_test_123")
        self.assertEqual(self.subscription.status, "ACTIVE")
        self.assertIsNotNone(self.subscription.end_date)
        self.assertTrue(
            BillingHistory.objects.filter(
                subscription=self.subscription,
                event_type="PAYMENT_SUCCEEDED",
            ).exists()
        )

    @patch("billing.views.verify_webhook_signature", return_value=True)
    def test_payment_failed_marks_transaction_failed(self, mock_verify):
        payment = self.create_payment()

        response = self.send_webhook(
            "payment.failed",
            {
                "id": "pay_failed_123",
                "order_id": payment.provider_order_id,
                "error_description": "Insufficient funds",
            },
            "event_failed_001",
        )

        payment.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payment.status, "FAILED")
        self.assertEqual(payment.failure_reason, "Insufficient funds")
        self.assertTrue(
            BillingHistory.objects.filter(
                subscription=self.subscription,
                event_type="PAYMENT_FAILED",
            ).exists()
        )

    @patch("billing.views.verify_webhook_signature", return_value=True)
    def test_duplicate_webhook_is_not_processed_twice(self, mock_verify):
        payment = self.create_payment()
        entity = {
            "id": "pay_duplicate_123",
            "order_id": payment.provider_order_id,
            "amount": 99900,
            "currency": "INR",
        }

        first_response = self.send_webhook(
            "payment.captured", entity, "event_duplicate_001"
        )
        second_response = self.send_webhook(
            "payment.captured", entity, "event_duplicate_001"
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertIn("already processed", second_response.data["message"])

        self.assertEqual(
            BillingHistory.objects.filter(
                subscription=self.subscription,
                event_type="PAYMENT_SUCCEEDED",
            ).count(),
            1,
        )
        self.assertEqual(
            ProcessedWebhookEvent.objects.filter(
                event_id="event_duplicate_001"
            ).count(),
            1,
        )

    @patch("billing.views.verify_webhook_signature", return_value=True)
    def test_processed_refund_marks_payment_refunded(self, mock_verify):
        payment = self.create_payment()

        capture_response = self.send_webhook(
            "payment.captured",
            {
                "id": "pay_refund_123",
                "order_id": payment.provider_order_id,
                "amount": 99900,
                "currency": "INR",
            },
            "event_refund_capture_001",
        )

        self.assertEqual(capture_response.status_code, status.HTTP_200_OK)

        refund_response = self.send_webhook(
            "refund.processed",
            {
                "id": "rfnd_test_123",
                "payment_id": "pay_refund_123",
                "amount": 99900,
            },
            "event_refund_001",
        )

        payment.refresh_from_db()

        self.assertEqual(refund_response.status_code, status.HTTP_200_OK)
        self.assertEqual(payment.status, "REFUNDED")
        self.assertTrue(
            BillingHistory.objects.filter(
                subscription=self.subscription,
                event_type="REFUND_ISSUED",
            ).exists()
        )

    
    @patch("billing.views.verify_webhook_signature", return_value=True)
    def test_duplicate_refund_id_is_not_counted_twice(self, mock_verify):
        payment = self.create_payment()

        self.send_webhook(
            "payment.captured",
            {
                "id": "pay_duplicate_refund_123",
                "order_id": payment.provider_order_id,
                "amount": 99900,
                "currency": "INR",
            },
            "event_capture_for_refund_001",
        )

        refund_entity = {
            "id": "rfnd_duplicate_123",
            "payment_id": "pay_duplicate_refund_123",
            "amount": 25000,
        }

        first_response = self.send_webhook(
            "refund.processed",
            refund_entity,
            "event_refund_first_001",
        )
        second_response = self.send_webhook(
            "refund.processed",
            refund_entity,
            "event_refund_second_001",
        )

        payment.refresh_from_db()

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(payment.refunded_amount, Decimal("250.00"))
        self.assertEqual(payment.status, "SUCCESS")
        self.assertEqual(
            BillingHistory.objects.filter(
                subscription=self.subscription,
                event_type="REFUND_ISSUED",
            ).count(),
            1,
        )