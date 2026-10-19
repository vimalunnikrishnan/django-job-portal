from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from billing.models import (
    BillingHistory,
    PaymentTransaction,
    SubscriptionPlan,
    UserSubscription,
)


class PaymentVerificationTest(APITestCase):
    verify_url = "/api/billing/verify-payment/"

    def setUp(self):
        self.employer = User.objects.create_user(
            username="verifyemployer",
            email="verifyemployer@example.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.plan = SubscriptionPlan.objects.create(
            name="PRO",
            description="Pro subscription for verification tests.",
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

        self.payment = PaymentTransaction.objects.create(
            subscription=self.subscription,
            amount=Decimal("999.00"),
            currency="INR",
            status="PENDING",
            provider="Razorpay",
            provider_order_id="order_verify_123",
        )

        self.client.force_authenticate(user=self.employer)

        self.valid_request = {
            "razorpay_order_id": "order_verify_123",
            "razorpay_payment_id": "pay_verify_123",
            "razorpay_signature": "test-signature",
        }

        self.captured_payment = {
            "id": "pay_verify_123",
            "order_id": "order_verify_123",
            "amount": 99900,
            "currency": "INR",
            "status": "captured",
        }

    @patch("billing.views.verify_payment_signature", return_value=False)
    def test_invalid_signature_is_rejected(self, mock_verify):
        response = self.client.post(
            self.verify_url,
            self.valid_request,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "PENDING")
        mock_verify.assert_called_once()

    @patch("billing.views.fetch_razorpay_payment")
    @patch("billing.views.verify_payment_signature", return_value=True)
    def test_mismatched_order_id_is_rejected(
        self, mock_signature, mock_fetch
    ):
        mock_fetch.return_value = {
            **self.captured_payment,
            "order_id": "order_wrong_123",
        }

        response = self.client.post(
            self.verify_url,
            self.valid_request,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "PENDING")

    @patch("billing.views.fetch_razorpay_payment")
    @patch("billing.views.verify_payment_signature", return_value=True)
    def test_mismatched_amount_is_rejected(
        self, mock_signature, mock_fetch
    ):
        mock_fetch.return_value = {
            **self.captured_payment,
            "amount": 100,
        }

        response = self.client.post(
            self.verify_url,
            self.valid_request,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "PENDING")

    @patch("billing.views.fetch_razorpay_payment")
    @patch("billing.views.verify_payment_signature", return_value=True)
    def test_uncaptured_payment_is_rejected(
        self, mock_signature, mock_fetch
    ):
        mock_fetch.return_value = {
            **self.captured_payment,
            "status": "authorized",
        }

        response = self.client.post(
            self.verify_url,
            self.valid_request,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "PENDING")

    @patch("billing.views.fetch_razorpay_payment")
    @patch("billing.views.verify_payment_signature", return_value=True)
    def test_successful_verification_activates_subscription(
        self, mock_signature, mock_fetch
    ):
        mock_fetch.return_value = self.captured_payment

        response = self.client.post(
            self.verify_url,
            self.valid_request,
            format="json",
        )

        self.payment.refresh_from_db()
        self.subscription.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.payment.status, "SUCCESS")
        self.assertEqual(
            self.payment.provider_transaction_id,
            "pay_verify_123",
        )
        self.assertEqual(self.subscription.status, "ACTIVE")
        self.assertIsNotNone(self.subscription.start_date)
        self.assertIsNotNone(self.subscription.end_date)
        self.assertTrue(
            BillingHistory.objects.filter(
                subscription=self.subscription,
                event_type="PAYMENT_SUCCEEDED",
            ).exists()
        )

    @patch("billing.views.fetch_razorpay_payment")
    @patch("billing.views.verify_payment_signature", return_value=True)
    def test_mismatched_currency_is_rejected(
        self, mock_signature, mock_fetch
    ):
        mock_fetch.return_value = {
            **self.captured_payment,
            "currency": "USD",
        }

        response = self.client.post(
            self.verify_url,
            self.valid_request,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "PENDING")
