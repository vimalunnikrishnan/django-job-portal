import os
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import CandidateProfile, EmailDeliveryLog, Notification, User
from accounts.services.ats_scoring import (
    calculate_ats_score,
    calculate_education_score,
    calculate_experience_score,
    calculate_skill_score,
)
from accounts.services.auto_shortlisting import auto_process_application
from accounts.services.batch_processing import auto_process_applications
from accounts.services.email_retry_service import retry_failed_email
from accounts.services.email_service import send_notification_email
from accounts.services.notification_service import (
    create_application_notification,
)
from accounts.services.resume_encryption import (
    decrypt_resume,
    encrypt_resume,
)
from accounts.services.resume_nlp import (
    extract_education,
    extract_experience_years,
    extract_keywords,
    extract_roles,
    extract_skills,
    parse_resume,
)
from jobs.models import Application, Job


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
        # Save original S3 storage.
        resume_field = CandidateProfile._meta.get_field("resume")
        original_storage = resume_field.storage

        # Use local storage during this test.
        storage = FileSystemStorage(
            location=os.path.join(os.getcwd(), "test_media")
        )
        resume_field.storage = storage

        # Restore original S3 storage after the test.
        self.addCleanup(
            setattr,
            resume_field,
            "storage",
            original_storage,
        )

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

        # The API must not expose internal exception details.
        if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            self.assertEqual(
                response.data["errors"]["detail"],
                "Unable to parse resume.",
            )
            self.assertEqual(
                response.data["errors"]["error"],
                "Internal resume processing error.",
            )


class ATSScoringServiceTest(TestCase):

    def test_calculate_skill_score(self):
        score = calculate_skill_score(
            "Python, Django, React",
            "Python, Django",
        )
        self.assertEqual(score, 66.67)

    def test_calculate_skill_score_without_required_skills(self):
        score = calculate_skill_score("", "Python, Django")
        self.assertEqual(score, 0)

    def test_calculate_experience_score(self):
        score = calculate_experience_score(4, 2)
        self.assertEqual(score, 50)

    def test_experience_score_capped_at_100(self):
        score = calculate_experience_score(3, 5)
        self.assertEqual(score, 100)

    def test_calculate_education_score(self):
        score = calculate_education_score(
            ["BCA", "MCA"],
            "bca",
        )
        self.assertEqual(score, 100)

    def test_education_score_without_candidate_education(self):
        score = calculate_education_score(["BCA"], "")
        self.assertEqual(score, 0)

    def test_calculate_ats_score(self):
        score = calculate_ats_score(80, 60, 100)
        self.assertEqual(score, 78)


class AutoShortlistingServiceTest(TestCase):

    def setUp(self):
        self.candidate = User.objects.create_user(
            username="shortlistcandidate",
            email="shortlistcandidate@gmail.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        self.employer = User.objects.create_user(
            username="shortlistemployer",
            email="shortlistemployer@gmail.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.candidate_profile = self.candidate.candidate_profile

        self.job = Job.objects.create(
            employer=self.employer,
            title="Python Developer",
            description="Python backend development",
            skills="Python, Django",
            experience=1,
            location="Kochi",
            job_type="FULL_TIME",
            status="OPEN",
            is_active=True,
        )

        self.application = Application.objects.create(
            candidate=self.candidate,
            job=self.job,
        )

    @patch("accounts.services.auto_shortlisting.calculate_and_save_ats_score")
    def test_application_is_shortlisted(self, mock_ats):
        mock_ats.return_value = Mock(match_percentage=85)

        result = auto_process_application(self.application)

        self.application.refresh_from_db()

        self.assertEqual(self.application.status, "SHORTLISTED")
        self.assertEqual(result["eligibility"]["action"], "SHORTLIST")
        self.assertTrue(
            Notification.objects.filter(
                user=self.candidate,
                notification_type="SHORTLISTED",
            ).exists()
        )

    @patch("accounts.services.auto_shortlisting.calculate_and_save_ats_score")
    def test_application_is_rejected(self, mock_ats):
        mock_ats.return_value = Mock(match_percentage=50)

        result = auto_process_application(self.application)

        self.application.refresh_from_db()

        self.assertEqual(self.application.status, "REJECTED")
        self.assertEqual(result["eligibility"]["action"], "REJECT")
        self.assertTrue(
            Notification.objects.filter(
                user=self.candidate,
                notification_type="REJECTED",
            ).exists()
        )

    @patch("accounts.services.auto_shortlisting.create_application_notification")
    @patch("accounts.services.auto_shortlisting.calculate_and_save_ats_score")
    def test_notification_failure_rolls_back_changes(
        self,
        mock_ats,
        mock_notification,
    ):
        mock_ats.return_value = Mock(match_percentage=85)
        mock_notification.side_effect = RuntimeError(
            "Notification creation failed."
        )

        with self.assertRaises(RuntimeError):
            auto_process_application(self.application)

        self.application.refresh_from_db()

        self.assertEqual(self.application.status, "APPLIED")


class BatchProcessingServiceTest(TestCase):

    def setUp(self):
        self.candidate = User.objects.create_user(
            username="batchcandidate",
            email="batchcandidate@gmail.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        self.employer = User.objects.create_user(
            username="batchemployer",
            email="batchemployer@gmail.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.job = Job.objects.create(
            employer=self.employer,
            title="Python Developer",
            description="Python backend development",
            skills="Python, Django",
            experience=1,
            location="Kochi",
            job_type="FULL_TIME",
            status="OPEN",
            is_active=True,
        )

        self.application = Application.objects.create(
            candidate=self.candidate,
            job=self.job,
        )

    @patch("accounts.services.batch_processing.auto_process_application")
    def test_batch_processes_successful_application(self, mock_process):
        mock_process.return_value = {"success": True}

        results = auto_process_applications()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], {"success": True})
        mock_process.assert_called_once()

    @patch("accounts.services.batch_processing.auto_process_application")
    def test_batch_continues_after_application_failure(self, mock_process):
        second_candidate = User.objects.create_user(
            username="batchcandidate2",
            email="batchcandidate2@gmail.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        Application.objects.create(
            candidate=second_candidate,
            job=self.job,
        )

        mock_process.side_effect = [
            RuntimeError("Processing failed."),
            {"success": True},
        ]

        results = auto_process_applications()

        self.assertEqual(len(results), 2)
        self.assertFalse(results[0]["success"])
        self.assertEqual(results[0]["error"], "Processing failed.")
        self.assertEqual(results[1], {"success": True})
        self.assertEqual(mock_process.call_count, 2)


class ResumeNLPServiceTest(TestCase):

    def test_extract_keywords(self):
        result = extract_keywords(
            "Python and Django are useful backend technologies."
        )

        self.assertIn("Python", result)
        self.assertIn("Django", result)
        self.assertEqual(len(result), len(set(result)))

    def test_extract_skills(self):
        result = extract_skills(
            "Experienced in Python, Django REST Framework and PostgreSQL."
        )

        self.assertEqual(
            result,
            [
                "Python",
                "Django",
                "Django REST Framework",
                "PostgreSQL",
            ],
        )

    def test_extract_experience_years(self):
        result = extract_experience_years(
            "I have 3.5 years of experience."
        )

        self.assertEqual(result, 3.5)

    def test_extract_roles(self):
        result = extract_roles(
            "Worked as a Python Developer and Backend Developer."
        )

        self.assertEqual(
            result,
            ["Python Developer", "Backend Developer"],
        )

    def test_extract_education(self):
        result = extract_education(
            "Bachelor of Computer Applications and MCA."
        )

        self.assertEqual(result, ["BCA", "MCA"])

    def test_parse_resume(self):
        result = parse_resume(
            "Python Developer with 2 years of experience. "
            "Bachelor of Computer Applications."
        )

        self.assertEqual(result["skills"], ["Python"])
        self.assertEqual(result["experience"]["years"], 2.0)
        self.assertEqual(
            result["experience"]["roles"],
            ["Python Developer"],
        )
        self.assertEqual(result["education"], ["BCA"])


class ResumeEncryptionServiceTest(TestCase):

    @patch.dict(
        os.environ,
        {"RESUME_ENCRYPTION_KEY": Fernet.generate_key().decode()},
    )
    def test_encrypt_and_decrypt_resume(self):
        original_content = b"Sample resume content"

        encrypted_content = encrypt_resume(original_content)
        decrypted_content = decrypt_resume(encrypted_content)

        self.assertNotEqual(encrypted_content, original_content)
        self.assertEqual(decrypted_content, original_content)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_encryption_key(self):
        with self.assertRaises(ImproperlyConfigured):
            encrypt_resume(b"Sample resume")

    @patch.dict(
        os.environ,
        {"RESUME_ENCRYPTION_KEY": "invalid-key"},
    )
    def test_invalid_encryption_key(self):
        with self.assertRaises(ImproperlyConfigured):
            encrypt_resume(b"Sample resume")

    @patch.dict(
        os.environ,
        {"RESUME_ENCRYPTION_KEY": Fernet.generate_key().decode()},
    )
    def test_decryption_with_wrong_key(self):
        encrypted_content = encrypt_resume(b"Sample resume")

        wrong_key = Fernet.generate_key().decode()

        with patch.dict(
            os.environ,
            {"RESUME_ENCRYPTION_KEY": wrong_key},
        ):
            with self.assertRaises(ValueError):
                decrypt_resume(encrypted_content)


class EmailRetryServiceTest(TestCase):

    def setUp(self):
        self.delivery_log = EmailDeliveryLog.objects.create(
            recipient_email="candidate@example.com",
            subject="Interview Update",
            template_name="interview_scheduled",
            notification_type="INTERVIEW",
            context={"candidate_name": "Test Candidate"},
            status="FAILED",
            attempt_count=1,
        )

    @patch(
        "accounts.services.email_retry_service.send_notification_email"
    )
    def test_successful_email_retry(self, mock_send):
        mock_send.return_value = True

        result = retry_failed_email(self.delivery_log.id)

        self.assertTrue(result["success"])
        self.assertEqual(
            result["message"],
            "Email retry successful.",
        )
        mock_send.assert_called_once()

    @patch(
        "accounts.services.email_retry_service.send_notification_email"
    )
    def test_already_sent_email_is_not_retried(self, mock_send):
        self.delivery_log.status = "SENT"
        self.delivery_log.save(update_fields=["status"])

        result = retry_failed_email(self.delivery_log.id)

        self.assertTrue(result["success"])
        mock_send.assert_not_called()

    @patch(
        "accounts.services.email_retry_service.send_notification_email"
    )
    def test_maximum_retry_limit(self, mock_send):
        self.delivery_log.attempt_count = 3
        self.delivery_log.save(update_fields=["attempt_count"])

        result = retry_failed_email(self.delivery_log.id)

        self.assertFalse(result["success"])
        self.assertEqual(
            result["message"],
            "Maximum retry attempts reached.",
        )
        mock_send.assert_not_called()

    @patch(
        "accounts.services.email_retry_service.send_notification_email"
    )
    def test_failed_email_retry(self, mock_send):
        mock_send.side_effect = Exception("SMTP unavailable")

        result = retry_failed_email(self.delivery_log.id)

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "SMTP unavailable")


class EmailServiceTest(TestCase):

    def setUp(self):
        self.email_data = {
            "recipient_email": "candidate@example.com",
            "subject": "Interview Update",
            "template_name": "interview_scheduled",
            "context": {"candidate_name": "Test Candidate"},
            "notification_type": "INTERVIEW",
        }

    @patch("accounts.services.email_service.render_email_template")
    @patch("accounts.services.email_service.send_mail")
    def test_successful_email_delivery(
        self, mock_send_mail, mock_render
    ):
        mock_render.return_value = "Test email message"
        mock_send_mail.return_value = 1

        result = send_notification_email(**self.email_data)

        delivery_log = EmailDeliveryLog.objects.get(
            recipient_email="candidate@example.com"
        )

        self.assertEqual(result, 1)
        self.assertEqual(delivery_log.status, "SENT")
        self.assertEqual(delivery_log.attempt_count, 1)
        self.assertEqual(delivery_log.error_message, "")

    @patch("accounts.services.email_service.render_email_template")
    @patch("accounts.services.email_service.send_mail")
    def test_failed_email_delivery(
        self, mock_send_mail, mock_render
    ):
        mock_render.return_value = "Test email message"
        mock_send_mail.return_value = 0

        result = send_notification_email(**self.email_data)

        delivery_log = EmailDeliveryLog.objects.get(
            recipient_email="candidate@example.com"
        )

        self.assertEqual(result, 0)
        self.assertEqual(delivery_log.status, "FAILED")
        self.assertEqual(delivery_log.attempt_count, 1)

    @patch("accounts.services.email_service.render_email_template")
    @patch("accounts.services.email_service.send_mail")
    def test_email_exception_is_logged_and_raised(
        self, mock_send_mail, mock_render
    ):
        mock_render.return_value = "Test email message"
        mock_send_mail.side_effect = Exception("SMTP unavailable")

        with self.assertRaisesMessage(
            Exception, "SMTP unavailable"
        ):
            send_notification_email(**self.email_data)

        delivery_log = EmailDeliveryLog.objects.get(
            recipient_email="candidate@example.com"
        )

        self.assertEqual(delivery_log.status, "FAILED")
        self.assertEqual(delivery_log.attempt_count, 1)
        self.assertEqual(
            delivery_log.error_message,
            "SMTP unavailable",
        )


class ApplicationNotificationServiceTest(TestCase):

    def setUp(self):
        self.candidate = User.objects.create_user(
            username="notificationcandidate",
            email="notificationcandidate@gmail.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        self.employer = User.objects.create_user(
            username="notificationemployer",
            email="notificationemployer@gmail.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.job = Job.objects.create(
            employer=self.employer,
            title="Python Developer",
            description="Python backend development",
            skills="Python, Django",
            experience=1,
            location="Kochi",
            job_type="FULL_TIME",
            status="OPEN",
            is_active=True,
        )

        self.application = Application.objects.create(
            candidate=self.candidate,
            job=self.job,
        )

    def test_creates_shortlisted_notification(self):
        notification = create_application_notification(
            self.application,
            "SHORTLISTED",
        )

        self.assertEqual(notification.user, self.candidate)
        self.assertEqual(
            notification.title,
            "Application Shortlisted",
        )
        self.assertIn("Python Developer", notification.message)

    def test_creates_rejected_notification(self):
        notification = create_application_notification(
            self.application,
            "REJECTED",
        )

        self.assertEqual(notification.title, "Application Update")
        self.assertIn("rejected", notification.message)

    def test_creates_interview_notification(self):
        notification = create_application_notification(
            self.application,
            "INTERVIEW",
        )

        self.assertEqual(notification.title, "Interview Scheduled")
        self.assertIn("Python Developer", notification.message)

    def test_returns_existing_unread_notification(self):
        existing = create_application_notification(
            self.application,
            "SHORTLISTED",
        )

        result = create_application_notification(
            self.application,
            "SHORTLISTED",
        )

        self.assertEqual(result.id, existing.id)
        self.assertEqual(Notification.objects.count(), 1)

    def test_creates_new_notification_if_previous_is_read(self):
        existing = create_application_notification(
            self.application,
            "SHORTLISTED",
        )

        existing.is_read = True
        existing.save(update_fields=["is_read"])

        new_notification = create_application_notification(
            self.application,
            "SHORTLISTED",
        )

        self.assertNotEqual(new_notification.id, existing.id)
        self.assertEqual(Notification.objects.count(), 2)

    def test_unknown_notification_type_uses_default_message(self):
        notification = create_application_notification(
            self.application,
            "UPDATED",
        )

        self.assertEqual(notification.title, "Application Update")
        self.assertIn("has been updated", notification.message)