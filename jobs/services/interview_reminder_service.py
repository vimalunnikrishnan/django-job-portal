
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from jobs.models import InterviewReminder, InterviewSchedule

from accounts.services.notification_email_service import (
    send_notification_email,
)



class InterviewReminderService:
    REMINDER_STAGES = {
        "24_HOURS": timedelta(hours=24),
        "1_HOUR": timedelta(hours=1),
        "15_MINUTES": timedelta(minutes=15),
    }

    @staticmethod
    def get_due_schedules():
        now = timezone.now()
        latest_reminder = now + timedelta(hours=24)

        return InterviewSchedule.objects.filter(
            status__in=["SCHEDULED", "CONFIRMED", "RESCHEDULED"],
            scheduled_start__gt=now,
            scheduled_start__lte=latest_reminder,
        ).select_related(
            "interview",
            "interview__application",
            "interview__application__candidate",
            "interview__application__job",
        )


    @staticmethod
    def get_retryable_reminders():
        now = timezone.now()
        retry_cutoff = now - timedelta(minutes=5)

        return InterviewReminder.objects.filter(
            status="FAILED",
            updated_at__lte=retry_cutoff,
            schedule__status__in=[
                "SCHEDULED",
                "CONFIRMED",
                "RESCHEDULED",
            ],
            schedule__scheduled_start__gt=now,
            attempt_count__lt=3,
        ).select_related(
            "schedule",
            "schedule__interview",
            "schedule__interview__application",
            "schedule__interview__application__candidate",
            "schedule__interview__application__job",
        )

    @classmethod
    def get_due_stages(cls, schedule, now=None):
        if now is None:
            now = timezone.now()

        time_until_interview = schedule.scheduled_start - now
        due_stages = []

        for stage, offset in cls.REMINDER_STAGES.items():
            # Trigger each reminder within a 5-minute window
            window_start = offset - timedelta(minutes=5)
            if window_start <= time_until_interview <= offset:
                due_stages.append(stage)

        return due_stages

    @staticmethod
    @transaction.atomic
    def get_or_create_reminder(schedule, stage):
        reminder, created = InterviewReminder.objects.get_or_create(
            schedule=schedule,
            stage=stage,
            defaults={"status": "PENDING"},
        )
        return reminder, created

    @classmethod
    def send_reminder(cls, schedule, stage):
        reminder, _ = cls.get_or_create_reminder(schedule, stage)

        if reminder.status == "SENT":
            return {
                "status": "SENT",
                "message": "Reminder was already sent.",
        }

        if schedule.status not in ["SCHEDULED", "CONFIRMED", "RESCHEDULED"]:
            return {
                "status": "SKIPPED",
                "message": "Interview is no longer scheduled.",
        }

        if schedule.scheduled_start <= timezone.now():
            return {
                "status": "SKIPPED",
                "message": "Interview start time has passed.",
        }

        interview = schedule.interview
        application = interview.application
        candidate = application.candidate
        job = application.job

        reminder.attempt_count += 1
        reminder.save(update_fields=["attempt_count", "updated_at"])

        try:
            result = send_notification_email(
                recipient_email=candidate.email,
                subject=f"Interview Reminder: {stage.replace('_', ' ').title()}",
                template_name="interview_reminder",
                context={
                    "candidate_name": (
                        candidate.get_full_name() or candidate.username
                    ),
                    "job_title": job.title,
                    "scheduled_start": schedule.scheduled_start.isoformat(),
                    "scheduled_end": schedule.scheduled_end.isoformat(),
                    "reminder_stage": stage.replace("_", " ").title(),
                },
                notification_type="INTERVIEW",
            )

            if result:
                reminder.status = "SENT"
                reminder.sent_at = timezone.now()
                reminder.error_message = ""
            else:
                reminder.status = "FAILED"
                reminder.error_message = "Email backend returned 0."

            reminder.save(
                update_fields=[
                    "status",
                    "sent_at",
                    "error_message",
                    "updated_at",
                ]
            )

            return {
                "status": reminder.status,
                "reminder_id": reminder.id,
            }

        except Exception as exc:
            reminder.status = "FAILED"
            reminder.error_message = str(exc)
            reminder.save(
                update_fields=["status", "error_message", "updated_at"]
            )
            return {
                "status": "FAILED",
                "reminder_id": reminder.id,
                "message": str(exc),
            }
