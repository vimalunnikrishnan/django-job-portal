from datetime import timedelta

from django.utils import timezone

from accounts.models import User
from billing.models import UserSubscription, CandidateProfileAccess


SUBSCRIPTION_GRACE_PERIOD_DAYS = 3


def get_active_subscription(user):
    """
    Return the employer's current paid subscription.
    Access continues during the 3-day grace period.
    Mark subscriptions expired after the grace period ends.
    """
    now = timezone.now()

    # Expire subscriptions whose grace period has ended.
    UserSubscription.objects.filter(
        user=user,
        status="ACTIVE",
        end_date__isnull=False,
        end_date__lte=now - timedelta(
            days=SUBSCRIPTION_GRACE_PERIOD_DAYS
        ),
    ).update(status="EXPIRED", updated_at=now)

    # Return a subscription that is active or still within grace.
    return (
        UserSubscription.objects
        .select_related("plan")
        .filter(
            user=user,
            status="ACTIVE",
            start_date__lte=now,
            end_date__gt=now - timedelta(
                days=SUBSCRIPTION_GRACE_PERIOD_DAYS
            ),
        )
        .order_by("-end_date")
        .first()
    )


def is_subscription_in_grace_period(subscription, now=None):
    """Return whether an expired subscription is within its grace period."""
    if now is None:
        now = timezone.now()

    if subscription.status != "ACTIVE" or subscription.end_date is None:
        return False

    grace_period_end = (
        subscription.end_date
        + timedelta(days=SUBSCRIPTION_GRACE_PERIOD_DAYS)
    )

    return subscription.end_date <= now < grace_period_end

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


def can_access_candidate(employer, candidate):
    """
    Check whether an employer can access a candidate profile.
    Record the candidate on the first permitted access.
    """
    if not isinstance(candidate, User):
        candidate = User.objects.get(
            pk=candidate,
            role="CANDIDATE",
        )

    subscription = get_active_subscription(employer)

    if subscription is None:
        from billing.models import SubscriptionPlan

        plan = SubscriptionPlan.objects.filter(
            name="FREE",
            is_active=True,
        ).first()

        if plan is None:
            return False, "The Free plan is not configured."

        candidate_limit = plan.candidate_access_limit
    else:
        candidate_limit = subscription.plan.candidate_access_limit

    # Already accessed candidates do not consume another allowance.
    already_accessed = CandidateProfileAccess.objects.filter(
        employer=employer,
        candidate=candidate,
    ).exists()

    if already_accessed:
        return True, ""

    # None means unlimited candidate access.
    if candidate_limit is not None:
        accessed_count = CandidateProfileAccess.objects.filter(
            employer=employer,
        ).count()

        if accessed_count >= candidate_limit:
            return (
                False,
                f"Your plan allows access to {candidate_limit} "
                "unique candidate profiles. Upgrade your plan "
                "to access more candidates.",
            )

    CandidateProfileAccess.objects.get_or_create(
        employer=employer,
        candidate=candidate,
    )

    return True, ""