from django.urls import path
from billing.views import (
    CreatePaymentOrderAPIView,
    SubscriptionStatusAPIView,
    VerifyPaymentAPIView,
    RazorpayWebhookAPIView,
    razorpay_test_page,
)

urlpatterns = [
    path(
        "create-order/",
        CreatePaymentOrderAPIView.as_view(),
        name="create-payment-order",
    ),
    path(
        "verify-payment/",
        VerifyPaymentAPIView.as_view(),
        name="verify-payment",
    ),
    path(
        "razorpay/webhook/",
        RazorpayWebhookAPIView.as_view(),
        name="razorpay-webhook",
    ),
    path(
        "test-checkout/",
        razorpay_test_page,
        name="razorpay-test-checkout",
    ),
    path(
        "subscription-status/",
        SubscriptionStatusAPIView.as_view(),
        name="subscription-status",
    ),
]