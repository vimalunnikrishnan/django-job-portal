from rest_framework.test import APITestCase
from rest_framework import status
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User


class UserModelTest(TestCase):

    def test_create_user(self):
        user = User.objects.create_user(
            username="testcandidate",
            email="testcandidate@gmail.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        self.assertEqual(user.email, "testcandidate@gmail.com")
        self.assertEqual(user.role, "CANDIDATE")
        self.assertTrue(user.check_password("TestPassword123"))
        self.assertTrue(user.is_active)


class LoginAPITest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="loginuser",
            email="loginuser@gmail.com",
            password="TestPassword123",
            role="CANDIDATE",
        )


    def test_profile_requires_authentication(self):
        response = self.client.get("/api/profile/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


    def test_login_with_invalid_password(self):
        response = self.client.post(
            "/api/login/",
            {
                "email": "loginuser@gmail.com",
                "password": "WrongPassword123",
            },
            format="json",
        )
    
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_with_valid_credentials(self):
        response = self.client.post(
            "/api/login/",
            {
                "email": "loginuser@gmail.com",
                "password": "TestPassword123",
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)


    def test_profile_with_authentication(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/profile/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["email"], "loginuser@gmail.com")
        self.assertEqual(response.data["data"]["role"], "CANDIDATE")


class ResumeUploadSecurityTest(APITestCase):

    def setUp(self):
        self.candidate = User.objects.create_user(
            username="resumecandidate",
            email="resumecandidate@gmail.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

    def test_invalid_resume_file_type_is_rejected(self):
        self.client.force_authenticate(user=self.candidate)

        invalid_file = SimpleUploadedFile(
            "malicious.exe",
            b"fake executable content",
            content_type="application/octet-stream",
        )

        response = self.client.post(
            "/api/upload-resume/",
            {"resume": invalid_file},
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn(
            "resume",
            response.data["errors"],
        )


    def test_resume_processing_error_does_not_expose_internal_exception(self):
        self.client.force_authenticate(user=self.candidate)

        resume = SimpleUploadedFile(
            "resume.pdf",
            b"test resume content",
            content_type="application/pdf",
        )

        response = self.client.post(
            "/api/upload-resume/",
            {"resume": resume},
            format="multipart",
        )

        # The test file may fail during parsing, but the API
        # must not expose the internal exception message.
        if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            self.assertEqual(
                response.data["errors"]["detail"],
                "Unable to parse resume.",
            )
            self.assertEqual(
                response.data["errors"]["error"],
                "Internal resume processing error.",
            )
