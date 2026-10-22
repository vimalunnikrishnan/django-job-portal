from rest_framework import serializers
from billing.models import PaymentTransaction
from billing.models import BillingHistory
from accounts.models import AuditTrail


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


class AdminPaymentTransactionSerializer(serializers.ModelSerializer):
    employer_email = serializers.EmailField(
        source="subscription.user.email",
        read_only=True,
    )
    plan_name = serializers.CharField(
        source="subscription.plan.name",
        read_only=True,
    )

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "subscription",
            "employer_email",
            "plan_name",
            "amount",
            "refunded_amount",
            "currency",
            "status",
            "provider",
            "provider_transaction_id",
            "provider_order_id",
            "failure_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AdminBillingHistorySerializer(serializers.ModelSerializer):
    employer_email = serializers.EmailField(
        source="subscription.user.email",
        read_only=True,
    )
    plan_name = serializers.CharField(
        source="subscription.plan.name",
        read_only=True,
    )

    class Meta:
        model = BillingHistory
        fields = [
            "id",
            "subscription",
            "employer_email",
            "plan_name",
            "event_type",
            "description",
            "amount",
            "created_at",
        ]
        read_only_fields = fields


class AdminFinancialAuditSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(
        source="actor.email",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = AuditTrail
        fields = [
            "id",
            "actor",
            "actor_email",
            "category",
            "action",
            "description",
            "target_type",
            "target_id",
            "metadata",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields