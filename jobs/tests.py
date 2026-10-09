from datetime import timedelta

from unittest.mock import patch
from jobs.models import Application, Job, AIInterview, AIInterviewSession, AIQuestion, AIAnswer, QuestionTemplate, JobQuestionMapping, AIAnswerEvaluation, InterviewAvailability, InterviewSchedule, InterviewReminder
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import User, CandidateProfile
from jobs.services.ai_bridge.base import AIRateLimitError
from jobs.services.ai_bridge.service import AIBridgeService
from jobs.services.ai_question_engine.engine import AIQuestionEngine
from jobs.services.ai_answer_evaluation.scoring import AnswerScoringEngine
from jobs.services.interview_reminder_service import InterviewReminderService

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


class AIQuestionEngineTest(TestCase):

    def setUp(self):
        self.candidate = User.objects.create_user(
            username="enginecandidate",
            email="enginecandidate@gmail.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        self.employer = User.objects.create_user(
            username="engineemployer",
            email="engineemployer@gmail.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.job = Job.objects.create(
            employer=self.employer,
            title="Python Developer",
            description="Python backend development",
            skills="Python, Django",
            experience=1,
            min_salary=25000,
            max_salary=45000,
            location="Kochi",
            job_type="FULL_TIME",
            status="OPEN",
            is_active=True,
        )

        self.application = Application.objects.create(
            candidate=self.candidate,
            job=self.job,
        )

        self.interview = AIInterview.objects.create(
            application=self.application,
        )

        self.session = AIInterviewSession.objects.create(
            interview=self.interview,
        )

        self.templates = [
            QuestionTemplate.objects.create(
                question="Tell me about yourself.",
                category="INTRODUCTION",
                order=1,
            ),
            QuestionTemplate.objects.create(
                question="How many years of software development experience do you have?",
                category="EXPERIENCE",
                order=2,
            ),
            QuestionTemplate.objects.create(
                question="What are your strongest Python and Django skills?",
                category="SKILLS",
                order=3,
            ),
            QuestionTemplate.objects.create(
                question="When are you available to join?",
                category="AVAILABILITY",
                order=4,
            ),
            QuestionTemplate.objects.create(
                question="What are your salary expectations?",
                category="SALARY",
                order=5,
            ),
        ]

        for index, template in enumerate(self.templates, start=1):
            JobQuestionMapping.objects.create(
                job=self.job,
                question_template=template,
                order=index,
            )

        self.engine = AIQuestionEngine(self.session)

    def test_get_question_set(self):
        questions = self.engine.get_question_set()

        self.assertEqual(questions.count(), 5)
        self.assertEqual(
            questions.first().question_template.question,
            "Tell me about yourself.",
        )

    def test_create_question(self):
        question = self.engine.get_next_question()

        self.assertEqual(
            question.question,
            "Tell me about yourself.",
        )
        self.assertEqual(question.sequence_number, 1)
        self.assertEqual(
            question.question_template,
            self.templates[0],
        )

    def test_save_answer(self):
        question = self.engine.get_next_question()

        answer = self.engine.save_answer(
            question,
            "I am a Python developer.",
        )

        self.assertEqual(
            answer.answer_text,
            "I am a Python developer.",
        )
        self.assertEqual(answer.question, question)

    def test_process_answer_moves_to_next_question(self):
        question = self.engine.get_next_question()

        result = self.engine.process_answer(
            question,
            "No",
        )

        self.assertEqual(result["action"], "NEXT")
        self.assertEqual(
            result["question"],
            "How many years of software development experience do you have?",
        )

    def test_interview_completion(self):
        self.session.current_question_index = 5
        self.session.save(
            update_fields=["current_question_index"]
        )

        self.assertTrue(
            self.engine.is_interview_complete()
        )


class AIAnswerEvaluationAPITest(APITestCase):

    def setUp(self):
        self.candidate = User.objects.create_user(
            username="evaluationcandidate",
            email="evaluationcandidate@gmail.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        self.employer = User.objects.create_user(
            username="evaluationemployer",
            email="evaluationemployer@gmail.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.job = Job.objects.create(
            employer=self.employer,
            title="Python Developer",
            description="Python backend development",
            skills="Python, Django",
            experience=1,
            min_salary=25000,
            max_salary=45000,
            location="Kochi",
            job_type="FULL_TIME",
            status="OPEN",
            is_active=True,
        )

        self.application = Application.objects.create(
            candidate=self.candidate,
            job=self.job,
        )

        self.interview = AIInterview.objects.create(
            application=self.application,
        )

        self.session = AIInterviewSession.objects.create(
            interview=self.interview,
        )

        self.question = AIQuestion.objects.create(
            session=self.session,
            question="What are your strongest Python and Django skills?",
            sequence_number=1,
        )

        self.client.force_authenticate(
            user=self.candidate
        )

    def test_submit_answer_and_create_evaluation(self):
        response = self.client.post(
            f"/api/jobs/ai-answers/{self.question.id}/evaluate/",
            {
                "answer_text": (
                    "I have strong Python and Django skills. "
                    "I have built backend web applications."
                )
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertTrue(
            AIAnswerEvaluation.objects.filter(
                answer__question=self.question
            ).exists()
        )

        evaluation = AIAnswerEvaluation.objects.get(
            answer__question=self.question
        )

        self.assertGreaterEqual(
            evaluation.overall_score,
            0,
        )

        self.assertLessEqual(
            evaluation.overall_score,
            100,
        )

    def test_retrieve_evaluation_score(self):
        answer = AIAnswer.objects.create(
            question=self.question,
            answer_text=(
                "I have strong Python and Django skills."
            ),
        )

        AIAnswerEvaluation.objects.create(
            answer=answer,
            relevance_score=80,
            completeness_score=75,
            keyword_score=100,
            overall_score=84.5,
            confidence=77.5,
            ai_annotations={
                "evaluation_method": "rule_based",
            },
        )

        response = self.client.get(
            f"/api/jobs/ai-answers/{self.question.id}/score/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["overall_score"],
            84.5,
        )

        self.assertEqual(
            response.data["keyword_score"],
            100,
        )


class AIInterviewSchedulingAPITest(APITestCase):

    def setUp(self):
        self.candidate = User.objects.create_user(
            username="schedulecandidate",
            email="schedulecandidate@gmail.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        self.employer = User.objects.create_user(
            username="scheduleemployer",
            email="scheduleemployer@gmail.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.other_employer = User.objects.create_user(
            username="other_schedule_employer",
            email="other_schedule_employer@gmail.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.job = Job.objects.create(
            employer=self.employer,
            title="Python Developer",
            description="Python backend development",
            skills="Python, Django",
            experience=1,
            min_salary=25000,
            max_salary=45000,
            location="Kochi",
            job_type="FULL_TIME",
            status="OPEN",
            is_active=True,
        )

        self.application = Application.objects.create(
            candidate=self.candidate,
            job=self.job,
        )

        self.interview = AIInterview.objects.create(
            application=self.application,
        )

        self.start_time = timezone.now() + timedelta(days=1)
        self.end_time = self.start_time + timedelta(minutes=30)

        self.slot = InterviewAvailability.objects.create(
            employer=self.employer,
            job=self.job,
            start_time=self.start_time,
            end_time=self.end_time,
        )

        self.client.force_authenticate(
            user=self.employer
        )

    def test_employer_can_create_availability_slot(self):
        new_start = timezone.now() + timedelta(days=2)
        new_end = new_start + timedelta(minutes=30)

        response = self.client.post(
            "/api/jobs/interview-availability/",
            {
                "job": self.job.id,
                "start_time": new_start.isoformat(),
                "end_time": new_end.isoformat(),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            InterviewAvailability.objects.filter(
                job=self.job,
                start_time=new_start,
            ).exists()
        )

    def test_employer_can_schedule_interview(self):
        response = self.client.post(
            "/api/jobs/interview-schedule/",
            {
                "interview_id": self.interview.id,
                "availability_id": self.slot.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertTrue(
            InterviewSchedule.objects.filter(
                interview=self.interview,
            ).exists()
        )

        self.slot.refresh_from_db()
        self.interview.refresh_from_db()

        self.assertFalse(self.slot.is_available)
        self.assertEqual(
            self.interview.status,
            "SCHEDULED",
        )

    def test_conflicting_slot_is_rejected(self):
        first_response = self.client.post(
            "/api/jobs/interview-schedule/",
            {
                "interview_id": self.interview.id,
                "availability_id": self.slot.id,
            },
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        second_interview = AIInterview.objects.create(
            application=Application.objects.create(
                candidate=User.objects.create_user(
                    username="secondcandidate",
                    email="secondcandidate@gmail.com",
                    password="TestPassword123",
                    role="CANDIDATE",
                ),
                job=self.job,
            )
        )

        conflicting_slot = InterviewAvailability.objects.create(
            employer=self.employer,
            job=self.job,
            start_time=self.start_time + timedelta(minutes=10),
            end_time=self.end_time + timedelta(minutes=10),
        )

        response = self.client.post(
            "/api/jobs/interview-schedule/",
            {
                "interview_id": second_interview.id,
                "availability_id": conflicting_slot.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertIn(
            "conflicts",
            response.data["errors"]["detail"].lower(),
        )

    def test_employer_can_reschedule_interview(self):
        schedule_response = self.client.post(
            "/api/jobs/interview-schedule/",
            {
                "interview_id": self.interview.id,
                "availability_id": self.slot.id,
            },
            format="json",
        )

        self.assertEqual(
            schedule_response.status_code,
            status.HTTP_201_CREATED,
        )

        new_start = timezone.now() + timedelta(days=2)
        new_end = new_start + timedelta(minutes=30)

        new_slot = InterviewAvailability.objects.create(
            employer=self.employer,
            job=self.job,
            start_time=new_start,
            end_time=new_end,
        )

        schedule = InterviewSchedule.objects.get(
            interview=self.interview,
        )

        response = self.client.post(
            "/api/jobs/interview-reschedule/",
            {
                "schedule_id": schedule.id,
                "availability_id": new_slot.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        schedule.refresh_from_db()
        self.slot.refresh_from_db()
        new_slot.refresh_from_db()

        self.assertEqual(
            schedule.status,
            "RESCHEDULED",
        )

        self.assertEqual(
            schedule.availability,
            new_slot,
        )

        self.assertTrue(self.slot.is_available)
        self.assertFalse(new_slot.is_available)

    def test_other_employer_cannot_schedule_interview(self):
        self.client.force_authenticate(
            user=self.other_employer
        )

        response = self.client.post(
            "/api/jobs/interview-schedule/",
            {
                "interview_id": self.interview.id,
                "availability_id": self.slot.id,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )



class InterviewReminderServiceTest(TestCase):
    def setUp(self):
        self.employer = User.objects.create_user(
            username="reminder_employer",
            email="reminder_employer@example.com",
            password="TestPassword123",
            role="EMPLOYER",
        )

        self.candidate = User.objects.create_user(
            username="reminder_candidate",
            email="reminder_candidate@example.com",
            password="TestPassword123",
            role="CANDIDATE",
        )

        self.job = Job.objects.create(
            employer=self.employer,
            title="Python Developer",
            description="Backend development",
            skills="Python, Django",
            experience=1,
            min_salary=25000,
            max_salary=45000,
            location="Kochi",
            job_type="FULL_TIME",
            status="OPEN",
            is_active=True,
            is_featured=False,
        )

        self.application = Application.objects.create(
            candidate=self.candidate,
            job=self.job,
        )

        self.interview = AIInterview.objects.create(
            application=self.application,
            status="SCHEDULED",
        )

        self.schedule = InterviewSchedule.objects.create(
            interview=self.interview,
            scheduled_start=timezone.now() + timedelta(hours=24),
            scheduled_end=timezone.now()
            + timedelta(hours=24, minutes=30),
            status="SCHEDULED",
        )

    def test_detects_24_hour_reminder_window(self):
        now = timezone.now()
        self.schedule.scheduled_start = now + timedelta(hours=24)
        self.schedule.save(update_fields=["scheduled_start"])

        stages = InterviewReminderService.get_due_stages(
            self.schedule,
            now=now,
        )

        self.assertIn("24_HOURS", stages)

    def test_detects_one_hour_reminder_window(self):
        now = timezone.now()
        self.schedule.scheduled_start = now + timedelta(hours=1)
        self.schedule.save(update_fields=["scheduled_start"])

        stages = InterviewReminderService.get_due_stages(
            self.schedule,
            now=now,
        )

        self.assertIn("1_HOUR", stages)

    def test_detects_15_minute_reminder_window(self):
        now = timezone.now()
        self.schedule.scheduled_start = now + timedelta(minutes=15)
        self.schedule.save(update_fields=["scheduled_start"])

        stages = InterviewReminderService.get_due_stages(
            self.schedule,
            now=now,
        )

        self.assertIn("15_MINUTES", stages)

    def test_get_or_create_prevents_duplicate_reminders(self):
        first, created_first = (
            InterviewReminderService.get_or_create_reminder(
                self.schedule,
                "24_HOURS",
            )
        )
        second, created_second = (
            InterviewReminderService.get_or_create_reminder(
                self.schedule,
                "24_HOURS",
            )
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            InterviewReminder.objects.filter(
                schedule=self.schedule,
                stage="24_HOURS",
            ).count(),
            1,
        )


    def test_failed_reminder_is_retryable_after_five_minutes(self):
        reminder = InterviewReminder.objects.create(
            schedule=self.schedule,
            stage="24_HOURS",
            status="FAILED",
            attempt_count=1,
        )

        InterviewReminder.objects.filter(pk=reminder.pk).update(
            updated_at=timezone.now() - timedelta(minutes=6)
        )

        retryable_ids = list(
            InterviewReminderService.get_retryable_reminders().values_list(
                "id",
                flat=True,
            )
        )

        self.assertIn(reminder.id, retryable_ids)

    def test_reminder_with_three_attempts_is_not_retryable(self):
        reminder = InterviewReminder.objects.create(
            schedule=self.schedule,
            stage="24_HOURS",
            status="FAILED",
            attempt_count=3,
        )

        InterviewReminder.objects.filter(pk=reminder.pk).update(
            updated_at=timezone.now() - timedelta(minutes=6)
        )

        retryable_ids = list(
            InterviewReminderService.get_retryable_reminders().values_list(
                "id",
                flat=True,
            )
        )

        self.assertNotIn(reminder.id, retryable_ids)
