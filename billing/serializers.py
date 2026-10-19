from rest_framework import serializers


class PaymentVerificationSerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )
    razorpay_payment_id = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )
    razorpay_signature = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
    )