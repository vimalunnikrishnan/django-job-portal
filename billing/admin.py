
from django.contrib import admin
from .models import (
    SubscriptionPlan,
    UserSubscription,
    PaymentTransaction,
    BillingHistory,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_days",
        "job_post_limit",
        "includes_analytics",
        "is_active",
    )
    list_filter = ("name", "is_active", "includes_analytics")
    search_fields = ("name", "description")


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "start_date", "end_date")
    list_filter = ("status", "plan")
    search_fields = ("user__email",)


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "subscription", "amount", "currency", "status", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("provider_transaction_id",)


@admin.register(BillingHistory)
class BillingHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "subscription", "event_type", "amount", "created_at")
    list_filter = ("event_type",)
