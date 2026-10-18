from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from billing.models import SubscriptionPlan, UserSubscription
from billing.services import can_create_job
from jobs.models import Job


class SubscriptionAccessTest(APITestCase):
    def test_free_employer_is_denied_analytics(self):
        self.activate_plan(self.free_plan)

        response = self.client.get(self.analytics_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pro_employer_is_denied_analytics(self):
        self.activate_plan(self.pro_plan)

        response = self.client.get(self.analytics_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_active_enterprise_employer_can_access_analytics(self):
        self.activate_plan(self.enterprise_plan)

        response = self.client.get(self.analytics_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_expired_enterprise_employer_is_denied_analytics(self):
        UserSubscription.objects.create(
            user=self.employer,
            plan=self.enterprise_plan,
            status="ACTIVE",
            start_date=timezone.now() - timedelta(days=60),
            end_date=timezone.now() - timedelta(days=30),
        )

        response = self.client.get(self.analytics_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def setUp(self):
        self.employer = User.objects.create_user(
            username="billingemployer",
            email="billingemployer@example.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.free_plan = SubscriptionPlan.objects.create(
            name="FREE",
            description="Free plan with up to 3 job posts.",
            price="0.00",
            duration_days=30,
            job_post_limit=3,
            includes_analytics=False,
        )

        self.pro_plan = SubscriptionPlan.objects.create(
            name="PRO",
            description="Pro plan with unlimited job posts.",
            price="999.00",
            duration_days=30,
            job_post_limit=None,
            includes_analytics=False,
        )

        self.enterprise_plan = SubscriptionPlan.objects.create(
            name="ENTERPRISE",
            description="Unlimited jobs with premium AI analytics.",
            price="4999.00",
            duration_days=30,
            job_post_limit=None,
            includes_analytics=True,
        )

        self.analytics_url = "/api/jobs/employer/analytics/"
        self.client.force_authenticate(user=self.employer)
        cache.clear()

    def create_job(self, number):
        return Job.objects.create(
            employer=self.employer,
            title=f"Test Job {number}",
            description="Test job description",
            location="Kochi",
            job_type="FULL_TIME",
            status="OPEN",
            is_active=True,
        )

    def activate_plan(self, plan):
        return UserSubscription.objects.create(
            user=self.employer,
            plan=plan,
            status="ACTIVE",
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=30),
        )

    def test_free_plan_allows_three_active_jobs(self):
        # Two jobs already exist; the third should still be allowed.
        for number in range(1, 3):
            self.create_job(number)

        allowed, message = can_create_job(self.employer)

        self.assertTrue(allowed)
        self.assertEqual(message, "")

    def test_free_plan_blocks_fourth_active_job(self):
        for number in range(1, 4):
            self.create_job(number)

        allowed, message = can_create_job(self.employer)

        self.assertFalse(allowed)
        self.assertIn("maximum of 3", message)

    def test_pro_plan_allows_more_than_three_jobs(self):
        self.activate_plan(self.pro_plan)

        for number in range(1, 5):
            self.create_job(number)

        allowed, message = can_create_job(self.employer)

        self.assertTrue(allowed)
        self.assertEqual(message, "")

    def test_enterprise_plan_allows_unlimited_jobs(self):
        self.activate_plan(self.enterprise_plan)

        for number in range(1, 6):
            self.create_job(number)

        allowed, message = can_create_job(self.employer)

        self.assertTrue(allowed)
        self.assertEqual(message, "")

    def test_expired_subscription_falls_back_to_free_plan(self):
        UserSubscription.objects.create(
            user=self.employer,
            plan=self.pro_plan,
            status="ACTIVE",
            start_date=timezone.now() - timedelta(days=60),
            end_date=timezone.now() - timedelta(days=30),
        )

        for number in range(1, 4):
            self.create_job(number)

        allowed, message = can_create_job(self.employer)

        self.assertFalse(allowed)
        self.assertIn("maximum of 3", message)

    def test_missing_free_plan_blocks_job_creation(self):
        SubscriptionPlan.objects.filter(name="FREE").update(
            is_active=False
        )

        allowed, message = can_create_job(self.employer)

        self.assertFalse(allowed)
        self.assertEqual(message, "The Free plan is not configured.")

    
    def test_free_plan_cannot_access_premium_analytics(self):
        self.assertFalse(self.free_plan.includes_analytics)

    def test_pro_plan_cannot_access_premium_analytics(self):
        self.assertFalse(self.pro_plan.includes_analytics)

    def test_enterprise_plan_includes_premium_analytics(self):
        self.assertTrue(self.enterprise_plan.includes_analytics)

    def test_expired_enterprise_subscription_is_not_active(self):
        UserSubscription.objects.create(
            user=self.employer,
            plan=self.enterprise_plan,
            status="ACTIVE",
            start_date=timezone.now() - timedelta(days=60),
            end_date=timezone.now() - timedelta(days=30),
        )

        from billing.services import get_active_subscription

        subscription = get_active_subscription(self.employer)

        self.assertIsNone(subscription)

        self.analytics_url = "/api/jobs/employer/analytics/"
        self.client.force_authenticate(user=self.employer)
        cache.clear()
