from datetime import timedelta

from django.core.cache import cache
from django.http import response
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from billing.services import (
    get_active_subscription,
    can_create_job,
    can_access_candidate,
)

from accounts.models import User
from billing.models import CandidateProfileAccess
from billing.models import SubscriptionPlan, UserSubscription
from billing.services import get_active_subscription
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

        self.candidate = User.objects.create_user(
            username="billingcandidate",
            email="billingcandidate@example.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        self.free_plan = SubscriptionPlan.objects.create(
            name="FREE",
            description="Free plan with up to 3 job posts.",
            price="0.00",
            duration_days=30,
            job_post_limit=3,
            candidate_access_limit=10,
            includes_analytics=False,
        )

        self.pro_plan = SubscriptionPlan.objects.create(
            name="PRO",
            description="Pro plan with unlimited job posts.",
            price="999.00",
            duration_days=30,
            job_post_limit=None,
            candidate_access_limit=100,
            includes_analytics=False,
        )

        self.enterprise_plan = SubscriptionPlan.objects.create(
            name="ENTERPRISE",
            description="Unlimited jobs with premium AI analytics.",
            price="4999.00",
            duration_days=30,
            job_post_limit=None,
            candidate_access_limit=None,
            includes_analytics=True,
        )

        self.analytics_url = "/api/jobs/employer/analytics/"
        self.subscription_status_url = "/api/billing/subscription-status/"
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

        subscription = get_active_subscription(self.employer)

        self.assertIsNone(subscription)

        self.analytics_url = "/api/jobs/employer/analytics/"
        self.client.force_authenticate(user=self.employer)
        cache.clear()

    def test_active_subscription_status_returns_pro_plan(self):
        self.activate_plan(self.pro_plan)

        response = self.client.get(self.subscription_status_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["plan"], "PRO")
        self.assertTrue(response.data["data"]["is_active"])


    def test_expired_subscription_status_falls_back_to_free(self):
        UserSubscription.objects.create(
            user=self.employer,
            plan=self.pro_plan,
            status="ACTIVE",
            start_date=timezone.now() - timedelta(days=60),
            end_date=timezone.now() - timedelta(days=30),
        )

        response = self.client.get(self.subscription_status_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["plan"], "FREE")
        self.assertFalse(response.data["data"]["is_active"])


    def test_employer_without_paid_subscription_gets_free_plan(self):
        response = self.client.get(self.subscription_status_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["plan"], "FREE")
        self.assertFalse(response.data["data"]["is_active"])


    def test_candidate_cannot_access_subscription_status(self):
        self.client.force_authenticate(user=self.candidate)

        response = self.client.get(self.subscription_status_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    
    def test_free_plan_candidate_access_limit(self):
        # FREE plan allows 10 unique candidates.
        for _ in range(10):
            candidate = User.objects.create_user(
                username=f"free_candidate_{_}",
                email=f"free_candidate_{_}@example.com",
                password="TestPassword123",
                role="CANDIDATE",
            )
            allowed, message = can_access_candidate(
                self.employer,
                candidate,
            )
            self.assertTrue(allowed, message)

        extra_candidate = User.objects.create_user(
            username="free_candidate_extra",
            email="free_candidate_extra@example.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        allowed, message = can_access_candidate(
            self.employer,
            extra_candidate,
        )

        self.assertFalse(allowed)
        self.assertIn("10", message)

    def test_repeated_candidate_access_does_not_consume_limit(self):
        candidate = User.objects.create_user(
            username="repeated_candidate",
            email="repeated_candidate@example.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        first_allowed, _ = can_access_candidate(
            self.employer,
            candidate,
        )
        second_allowed, _ = can_access_candidate(
            self.employer,
            candidate,
        )

        self.assertTrue(first_allowed)
        self.assertTrue(second_allowed)
        self.assertEqual(
            CandidateProfileAccess.objects.filter(
                employer=self.employer,
                candidate=candidate,
            ).count(),
            1,
        )

    def test_enterprise_candidate_access_is_unlimited(self):
        self.activate_plan(self.enterprise_plan)

        for index in range(12):
            candidate = User.objects.create_user(
                username=f"enterprise_candidate_{index}",
                email=f"enterprise_candidate_{index}@example.com",
                password="TestPassword123",
                role="CANDIDATE",
            )

            allowed, message = can_access_candidate(
                self.employer,
                candidate,
            )
            self.assertTrue(allowed, message)

    
    def test_pro_plan_candidate_access_limit(self):
        self.activate_plan(self.pro_plan)

        for index in range(100):
            candidate = User.objects.create_user(
                username=f"pro_candidate_{index}",
                email=f"pro_candidate_{index}@example.com",
                password="TestPassword123",
                role="CANDIDATE",
            )

            allowed, message = can_access_candidate(
                self.employer,
                candidate,
            )
            self.assertTrue(allowed, message)

        extra_candidate = User.objects.create_user(
            username="pro_candidate_extra",
            email="pro_candidate_extra@example.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        allowed, message = can_access_candidate(
            self.employer,
            extra_candidate,
        )

        self.assertFalse(allowed)
        self.assertIn("100", message)



class SubscriptionGracePeriodTest(APITestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            username="grace_period_employer",
            email="grace_period_employer@example.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.plan = SubscriptionPlan.objects.create(
            name="PRO",
            description="Grace period test plan",
            price="499.00",
            duration_days=30,
            job_post_limit=None,
            candidate_access_limit=100,
            includes_analytics=False,
        )

    def create_subscription(self, end_date):
        return UserSubscription.objects.create(
            user=self.employer,
            plan=self.plan,
            status="ACTIVE",
            start_date=timezone.now() - timedelta(days=30),
            end_date=end_date,
        )

    def test_subscription_remains_available_during_grace_period(self):
        subscription = self.create_subscription(
            timezone.now() - timedelta(days=1)
        )

        active_subscription = get_active_subscription(self.employer)

        self.assertEqual(active_subscription, subscription)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "ACTIVE")

    def test_subscription_expires_after_grace_period(self):
        subscription = self.create_subscription(
            timezone.now() - timedelta(days=4)
        )

        active_subscription = get_active_subscription(self.employer)

        self.assertIsNone(active_subscription)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "EXPIRED")