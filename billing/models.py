
from django.conf import settings
from django.db import models
from django.utils import timezone


class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [
        ("FREE", "Free"),
        ("PRO", "Pro"),
        ("ENTERPRISE", "Enterprise"),
    ]

    name = models.CharField(max_length=20, choices=PLAN_CHOICES, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_days = models.PositiveIntegerField(default=30)
    job_post_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Leave blank for unlimited job posts.",
    )
    includes_analytics = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_name_display()} - {self.price}"


class UserSubscription(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("EXPIRED", "Expired"),
        ("CANCELLED", "Cancelled"),
        ("PENDING", "Pending"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        limit_choices_to={"role": "EMPLOYER"},
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_currently_active(self):
        now = timezone.now()
        return (
            self.status == "ACTIVE"
            and self.start_date is not None
            and self.end_date is not None
            and self.start_date <= now < self.end_date
        )

    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("REFUNDED", "Refunded"),
    ]

    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    refunded_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    provider = models.CharField(max_length=50, blank=True)
    provider_transaction_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )
    provider_order_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transaction {self.pk} - {self.amount} {self.currency}"


class BillingHistory(models.Model):
    EVENT_CHOICES = [
        ("SUBSCRIPTION_CREATED", "Subscription Created"),
        ("SUBSCRIPTION_ACTIVATED", "Subscription Activated"),
        ("SUBSCRIPTION_RENEWED", "Subscription Renewed"),
        ("SUBSCRIPTION_CANCELLED", "Subscription Cancelled"),
        ("PAYMENT_SUCCEEDED", "Payment Succeeded"),
        ("PAYMENT_FAILED", "Payment Failed"),
        ("REFUND_ISSUED", "Refund Issued"),
    ]

    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.PROTECT,
        related_name="billing_history",
    )
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    description = models.TextField(blank=True)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subscription_id} - {self.event_type}"


class ProcessedWebhookEvent(models.Model):
    provider = models.CharField(max_length=50, default="Razorpay")
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    refund_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider} - {self.event_type} - {self.event_id}"