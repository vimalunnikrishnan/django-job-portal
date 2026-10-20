import logging
from decimal import Decimal, ROUND_HALF_UP

import json

from django.db import transaction
from rest_framework.permissions import AllowAny

from .razorpay_service import verify_webhook_signature

from django.shortcuts import render
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import (
    BillingHistory,
    PaymentTransaction,
    ProcessedWebhookEvent,
    SubscriptionPlan,
    UserSubscription,
)
from .razorpay_service import (
    RazorpayServiceError,
    create_razorpay_order,
    fetch_razorpay_payment,
    verify_payment_signature,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)


class CreatePaymentOrderAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if getattr(request.user, "role", None) != "EMPLOYER":
            return Response(
                {
                    "success": False,
                    "message": "Only employers can purchase subscriptions.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        plan_id = request.data.get("plan_id")

        if not plan_id:
            return Response(
                {
                    "success": False,
                    "message": "plan_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan = SubscriptionPlan.objects.filter(
            id=plan_id,
            is_active=True,
        ).first()

        if plan is None:
            return Response(
                {
                    "success": False,
                    "message": "Subscription plan not found or inactive.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if plan.price <= Decimal("0.00"):
            return Response(
                {
                    "success": False,
                    "message": "A payment order is not required for the Free plan.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount_paise = int(
            (plan.price * Decimal("100")).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )

        try:
            with transaction.atomic():
                subscription = UserSubscription.objects.create(
                    user=request.user,
                    plan=plan,
                    status="PENDING",
                )

                payment = PaymentTransaction.objects.create(
                    subscription=subscription,
                    amount=plan.price,
                    currency="INR",
                    status="PENDING",
                    provider="Razorpay",
                )

                order = create_razorpay_order(
                    amount_paise=amount_paise,
                    receipt=f"billing-{payment.id}",
                    notes={
                        "payment_transaction_id": str(payment.id),
                        "subscription_id": str(subscription.id),
                    },
                )

                payment.provider_order_id = order["id"]
                payment.save(update_fields=["provider_order_id", "updated_at"])

        except RazorpayServiceError:
            logger.warning(
                "Unable to create payment order for user_id=%s",
                request.user.id,
            )
            return Response(
                {
                    "success": False,
                    "message": "Unable to create payment order. Please try again.",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "success": True,
                "message": "Payment order created.",
                "data": {
                    "subscription_id": subscription.id,
                    "payment_transaction_id": payment.id,
                    "razorpay_order_id": order["id"],
                    "amount": amount_paise,
                    "currency": "INR",
                    "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyPaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from billing.serializers import PaymentVerificationSerializer

        serializer = PaymentVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "message": "Invalid payment details.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        order_id = data["razorpay_order_id"]
        payment_id = data["razorpay_payment_id"]
        signature = data["razorpay_signature"]

        if getattr(request.user, "role", None) != "EMPLOYER":
            return Response(
                {"success": False, "message": "Only employers can verify payments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        payment = PaymentTransaction.objects.filter(
            provider_order_id=order_id,
            subscription__user=request.user,
            provider="Razorpay",
        ).select_related("subscription", "subscription__plan").first()

        if payment is None:
            return Response(
                {"success": False, "message": "Payment transaction not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if payment.status == "SUCCESS":
            if payment.provider_transaction_id == payment_id:
                return Response({
                    "success": True,
                    "message": "Payment was already verified.",
                })
            return Response(
                {"success": False, "message": "Transaction already completed."},
                status=status.HTTP_409_CONFLICT,
            )

        if payment.status != "PENDING":
            return Response(
                {"success": False, "message": "Transaction is not pending."},
                status=status.HTTP_409_CONFLICT,
            )

        if not verify_payment_signature(order_id, payment_id, signature):
            return Response(
                {"success": False, "message": "Payment signature verification failed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            razorpay_payment = fetch_razorpay_payment(payment_id)
        except RazorpayServiceError:
            return Response(
                {"success": False, "message": "Unable to verify payment with Razorpay."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if (
            razorpay_payment.get("order_id") != order_id
            or razorpay_payment.get("amount") != int(
                (payment.amount * Decimal("100")).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )
            or razorpay_payment.get("currency") != payment.currency
        ):
            return Response(
                {"success": False, "message": "Payment details do not match the transaction."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if razorpay_payment.get("status") != "captured":
            return Response(
                {
                    "success": False,
                    "message": "Payment is not captured yet.",
                    "payment_status": razorpay_payment.get("status"),
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            with transaction.atomic():
                payment = PaymentTransaction.objects.select_for_update().get(
                    pk=payment.pk
                )

                if payment.status == "SUCCESS":
                    if payment.provider_transaction_id == payment_id:
                        return Response({
                            "success": True,
                            "message": "Payment was already verified.",
                        })
                    return Response(
                        {"success": False, "message": "Transaction already completed."},
                        status=status.HTTP_409_CONFLICT,
                    )

                if payment.status != "PENDING":
                    return Response(
                        {"success": False, "message": "Transaction is not pending."},
                        status=status.HTTP_409_CONFLICT,
                    )

                subscription = UserSubscription.objects.select_for_update().get(
                    pk=payment.subscription_id
                )

                now = timezone.now()
                subscription.status = "ACTIVE"
                subscription.start_date = now
                subscription.end_date = now + timedelta(
                    days=subscription.plan.duration_days
                )
                subscription.save(
                    update_fields=[
                        "status",
                        "start_date",
                        "end_date",
                        "updated_at",
                    ]
                )

                payment.status = "SUCCESS"
                payment.provider_transaction_id = payment_id
                payment.save(
                    update_fields=[
                        "status",
                        "provider_transaction_id",
                        "updated_at",
                    ]
                )

                BillingHistory.objects.create(
                    subscription=subscription,
                    event_type="PAYMENT_SUCCEEDED",
                    description=f"Razorpay payment captured: {payment_id}",
                    amount=payment.amount,
                )

        except Exception:
            logger.exception(
                "Failed to finalize payment transaction_id=%s",
                payment.pk,
            )
            return Response(
                {"success": False, "message": "Unable to finalize payment."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "success": True,
                "message": "Payment verified and subscription activated.",
                "data": {
                    "subscription_id": subscription.id,
                    "payment_transaction_id": payment.id,
                    "subscription_status": subscription.status,
                    "subscription_end_date": subscription.end_date,
                },
            },
            status=status.HTTP_200_OK,
        )


class RazorpayWebhookAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from billing.models import ProcessedWebhookEvent

        payload = request.body
        signature = request.headers.get("X-Razorpay-Signature", "")

        if not verify_webhook_signature(payload, signature):
            return Response(
                {"success": False, "message": "Invalid webhook signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            event_data = json.loads(payload)
            event_type = event_data.get("event", "")
            event_id = request.headers.get("x-razorpay-event-id", "")
            payment_entity = (
                event_data.get("payload", {})
                .get("payment", {})
                .get("entity", {})
            )
            refund_entity = (
                event_data.get("payload", {})
                .get("refund", {})
                .get("entity", {})
            )
        except (ValueError, AttributeError):
            return Response(
                {"success": False, "message": "Invalid webhook payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        supported_events = {
            "payment.captured",
            "payment.failed",
            "refund.processed",
        }

        if event_type not in supported_events:
            return Response(
                {"success": True, "message": "Event ignored."},
                status=status.HTTP_200_OK,
            )

        if not event_id:
            return Response(
                {"success": False, "message": "Missing webhook event ID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                event, created = ProcessedWebhookEvent.objects.get_or_create(
                    event_id=event_id,
                    defaults={
                        "provider": "Razorpay",
                        "event_type": event_type,
                        "refund_id": (
                            refund_entity.get("id", "")
                            if event_type == "refund.processed"
                            else ""
                        ),
                    },
                )

                if not created:
                    return Response(
                        {"success": True, "message": "Event already processed."},
                        status=status.HTTP_200_OK,
                    )

                if event_type in {"payment.captured", "payment.failed"}:
                    order_id = payment_entity.get("order_id")
                    payment_id = payment_entity.get("id")

                    payment = PaymentTransaction.objects.select_for_update().filter(
                        provider_order_id=order_id,
                        provider="Razorpay",
                    ).select_related(
                        "subscription", "subscription__plan"
                    ).first()

                    if payment is None:
                        raise ValueError("Payment transaction not found.")

                    if event_type == "payment.captured":
                        expected_amount = int(
                            (payment.amount * Decimal("100")).quantize(
                                Decimal("1"), rounding=ROUND_HALF_UP
                            )
                        )

                        if (
                            payment_entity.get("amount") != expected_amount
                            or payment_entity.get("currency") != payment.currency
                        ):
                            raise ValueError("Captured payment details do not match.")

                        if payment.status == "FAILED":
                            raise ValueError("Cannot capture a failed transaction.")

                        if payment.status == "PENDING":
                            subscription = UserSubscription.objects.select_for_update().get(
                                pk=payment.subscription_id
                            )

                            now = timezone.now()
                            subscription.status = "ACTIVE"
                            subscription.start_date = now
                            subscription.end_date = now + timedelta(
                                days=subscription.plan.duration_days
                            )
                            subscription.save(
                                update_fields=[
                                    "status", "start_date", "end_date", "updated_at"
                                ]
                            )

                            payment.status = "SUCCESS"
                            payment.provider_transaction_id = payment_id
                            payment.save(
                                update_fields=[
                                    "status", "provider_transaction_id", "updated_at"
                                ]
                            )

                            BillingHistory.objects.create(
                                subscription=subscription,
                                event_type="PAYMENT_SUCCEEDED",
                                description=f"Razorpay payment captured: {payment_id}",
                                amount=payment.amount,
                            )

                    else:
                        if payment.status == "PENDING":
                            payment.status = "FAILED"
                            payment.failure_reason = (
                                payment_entity.get("error_description")
                                or "Payment failed."
                            )
                            payment.save(
                                update_fields=[
                                    "status", "failure_reason", "updated_at"
                                ]
                            )

                            BillingHistory.objects.create(
                                subscription=payment.subscription,
                                event_type="PAYMENT_FAILED",
                                description=payment.failure_reason,
                                amount=payment.amount,
                            )

                elif event_type == "refund.processed":
                    payment_id = refund_entity.get("payment_id")
                    refund_id = refund_entity.get("id")
                    if not refund_id:
                        raise ValueError("Missing refund ID.")

                    if ProcessedWebhookEvent.objects.filter(
                        refund_id=refund_id
                    ).exclude(event_id=event_id).exists():
                        return Response(
                            {"success": True, "message": "Refund already processed."},
                            status=status.HTTP_200_OK,
                        )
                    refund_amount_paise = refund_entity.get("amount")

                    if not isinstance(refund_amount_paise, int) or refund_amount_paise <= 0:
                        raise ValueError("Invalid refund amount.")

                    payment = PaymentTransaction.objects.select_for_update().filter(
                        provider_transaction_id=payment_id,
                        provider="Razorpay",
                    ).select_related("subscription").first()

                    if payment is None:
                        raise ValueError("Refund payment transaction not found.")

                    refund_amount = (
                        Decimal(refund_amount_paise) / Decimal("100")
                    ).quantize(Decimal("0.01"))

                    if payment.status not in {"SUCCESS", "REFUNDED"}:
                        raise ValueError("Payment is not eligible for a refund.")

                    new_refunded_amount = payment.refunded_amount + refund_amount

                    if new_refunded_amount > payment.amount:
                        raise ValueError("Refund amount exceeds the original payment.")

                    payment.refunded_amount = new_refunded_amount

                    if new_refunded_amount == payment.amount:
                        payment.status = "REFUNDED"

                    payment.save(
                        update_fields=[
                            "refunded_amount",
                            "status",
                            "updated_at",
                        ]
                    )

                    BillingHistory.objects.create(
                        subscription=payment.subscription,
                        event_type="REFUND_ISSUED",
                        description=f"Razorpay refund processed: {refund_id}",
                        amount=refund_amount,
                    )

        except ValueError as exc:
            logger.warning("Razorpay webhook rejected: %s", exc)
            return Response(
                {"success": False, "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("Failed to process Razorpay webhook event.")
            return Response(
                {"success": False, "message": "Webhook processing failed."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"success": True, "message": "Webhook processed."},
            status=status.HTTP_200_OK,
        )


def razorpay_test_page(request):
    return render(request, "billing/razorpay_test.html")
