from django.urls import path
from billing.views import (
    CreatePaymentOrderAPIView,
    VerifyPaymentAPIView,
    RazorpayWebhookAPIView,
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
]