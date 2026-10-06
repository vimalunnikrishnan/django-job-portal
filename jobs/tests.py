from jobs.models import Application, Job
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import User, CandidateProfile
from jobs.services.ai_bridge.base import AIRateLimitError
from jobs.services.ai_bridge.service import AIBridgeService


class JobCreationAPITest(APITestCase):

    def setUp(self):
        self.candidate = User.objects.create_user(
            username="jobcandidate",
            email="jobcandidate@gmail.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        self.employer = User.objects.create_user(
            username="jobemployer",
            email="jobemployer@gmail.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.candidate_profile = CandidateProfile.objects.get(
            user=self.candidate
        )

        self.job = Job.objects.create(
            employer=self.employer,
            title="Django Backend Developer",
            description="Backend development using Django",
            skills="Python, Django, DRF",
            experience=1,
            min_salary=25000,
            max_salary=45000,
            location="Kochi",
            job_type="FULL_TIME",
            status="OPEN",
            is_active=True,
            is_featured=False,
        )


    def test_candidate_cannot_apply_without_resume(self):
        self.client.force_authenticate(user=self.candidate)

        response = self.client.post(
            f"/api/jobs/{self.job.id}/apply/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["errors"]["detail"],
            "Please upload your resume before applying.",
        )


    def test_candidate_cannot_create_job(self):
        self.client.force_authenticate(user=self.candidate)

        response = self.client.post(
            "/api/jobs/",
            {
                "title": "Python Developer",
                "description": "Backend development role",
                "skills": "Python, Django, REST API",
                "experience": 1,
                "min_salary": 20000,
                "max_salary": 40000,
                "location": "Kochi",
                "job_type": "FULL_TIME",
                "status": "OPEN",
                "is_active": True,
                "is_featured": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


    def test_candidate_can_apply_with_resume(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        resume = SimpleUploadedFile(
            "resume.pdf",
            b"Test resume content",
            content_type="application/pdf",
        )

        self.candidate_profile.resume = resume
        self.candidate_profile.save()

        self.client.force_authenticate(user=self.candidate)

        response = self.client.post(
            f"/api/jobs/{self.job.id}/apply/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["data"]["job"],
            self.job.id,
        )
        self.assertEqual(
            response.data["data"]["candidate"],
            self.candidate.id,
        )


    def test_employer_can_create_job(self):
        self.client.force_authenticate(user=self.employer)

        response = self.client.post(
            "/api/jobs/",
            {
                "title": "Django Backend Developer",
                "description": "Backend development using Django and REST APIs",
                "skills": "Python, Django, DRF",
                "experience": 1,
                "min_salary": 25000,
                "max_salary": 45000,
                "location": "Kochi",
                "job_type": "FULL_TIME",
                "status": "OPEN",
                "is_active": True,
                "is_featured": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["data"]["title"], "Django Backend Developer")
        self.assertEqual(response.data["data"]["employer"], self.employer.id)


    def test_employer_cannot_auto_process_other_employers_application(self):
        other_employer = User.objects.create_user(
            username="otheremployer",
            email="otheremployer@gmail.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        from jobs.models import Application

        application = Application.objects.create(
            candidate=self.candidate,
            job=self.job,
        )

        self.client.force_authenticate(user=other_employer)

        response = self.client.post(
            f"/api/jobs/applications/{application.id}/auto-process/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )


    def test_employer_cannot_update_other_employers_application(self):
        other_employer = User.objects.create_user(
            username="statusotheremployer",
            email="statusotheremployer@gmail.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        from jobs.models import Application

        application = Application.objects.create(
            candidate=self.candidate,
            job=self.job,
        )

        self.client.force_authenticate(user=other_employer)

        response = self.client.patch(
            f"/api/jobs/applications/{application.id}/status/",
            {"status": "SHORTLISTED"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )


class AIBridgeServiceTest(TestCase):

    def test_generate_text_success(self):
        bridge = AIBridgeService()

        result = bridge.generate_text("Explain Django")

        self.assertTrue(result["success"])
        self.assertIn("Mock AI response", result["text"])


    def test_provider_exception_returns_safe_failure(self):
        provider = type(
            "FailProvider",
            (),
            {
                "generate_text": lambda self, prompt: (
                    (_ for _ in ()).throw(
                        ConnectionError("Test provider failure")
                    )
                )
            },
        )

        bridge = AIBridgeService(
            provider=provider(),
            max_retries=3,
        )

        result = bridge.generate_text("Test retry")

        self.assertFalse(result["success"])
        self.assertEqual(
            result["error"],
            "Test provider failure",
        )


    def test_rate_limit_returns_safe_failure(self):
        provider = type(
            "RateLimitProvider",
            (),
            {
                "generate_text": lambda self, prompt: (
                    (_ for _ in ()).throw(
                        AIRateLimitError()
                    )
                )
            },
        )

        bridge = AIBridgeService(
            provider=provider(),
            max_retries=3,
        )

        result = bridge.generate_text("Test rate limit")

        self.assertFalse(result["success"])
        self.assertEqual(
            result["error"],
            "AI provider rate limit exceeded.",
        )


    def test_make_call_returns_call_id(self):
        bridge = AIBridgeService()

        result = bridge.make_call(
            phone_number="+910000000000",
            voice="female",
            language="en",
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["call_id"],
            "MOCK-CALL-001",
        )
        self.assertEqual(result["voice"], "female")
        self.assertEqual(result["language"], "en")