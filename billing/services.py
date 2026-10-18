
from django.utils import timezone

from billing.models import UserSubscription


def get_active_subscription(user):
    """Return the employer's current active subscription, if one exists."""
    now = timezone.now()

    return (
        UserSubscription.objects
        .select_related("plan")
        .filter(
            user=user,
            status="ACTIVE",
            start_date__lte=now,
            end_date__gt=now,
        )
        .order_by("-end_date")
        .first()
    )


def can_create_job(user):
    """Check whether an employer can create another job post."""
    subscription = get_active_subscription(user)

    # No active subscription: use the Free plan as the fallback.
    if subscription is None:
        from billing.models import SubscriptionPlan

        free_plan = SubscriptionPlan.objects.filter(
            name="FREE",
            is_active=True,
        ).first()

        if free_plan is None:
            return False, "The Free plan is not configured."

        job_limit = free_plan.job_post_limit
    else:
        job_limit = subscription.plan.job_post_limit

    # None means unlimited job posts.
    if job_limit is None:
        return True, ""

    from jobs.models import Job

    existing_jobs = Job.objects.filter(
        employer=user,
        is_active=True,
    ).count()

    if existing_jobs >= job_limit:
        return (
            False,
            f"Your plan allows a maximum of {job_limit} active job posts. "
            "Upgrade your subscription to post more jobs.",
        )

    return True, ""