from django.utils import timezone

from jobs.models import (
    InterviewAvailability,
    InterviewSchedule,
)

from accounts.services.notification_email_service import (
    send_interview_scheduled_email,
)
from accounts.services.notification_service import (
    create_application_notification,
)


class AIInterviewScheduler:

    def get_available_slots(self, job):
        """Return active future availability slots for a job."""

        return InterviewAvailability.objects.filter(
            job=job,
            is_available=True,
            start_time__gte=timezone.now(),
        ).order_by("start_time")

    def validate_slot(self, slot):
        """Validate that an availability slot is usable."""

        now = timezone.now()

        if not slot.is_available:
            return False, "This slot is no longer available."

        if slot.start_time <= now:
            return False, "The interview slot must be in the future."

        if slot.end_time <= slot.start_time:
            return False, "Slot end time must be after start time."

        return True, None

    def has_conflict(self, start_time, end_time, exclude_schedule=None):
        """Check whether the requested time conflicts with another interview."""

        schedules = InterviewSchedule.objects.filter(
            scheduled_start__lt=end_time,
            scheduled_end__gt=start_time,
            status__in=[
                "SCHEDULED",
                "CONFIRMED",
                "RESCHEDULED",
            ],
        )

        if exclude_schedule:
            schedules = schedules.exclude(
                id=exclude_schedule.id
            )

        return schedules.exists()

    def schedule_interview(self, interview, slot):
        """Schedule an interview using an available slot."""

        is_valid, error = self.validate_slot(slot)

        if not is_valid:
            return {
                "success": False,
                "error": error,
            }

        if self.has_conflict(
            slot.start_time,
            slot.end_time,
        ):
            return {
                "success": False,
                "error": "This interview slot conflicts with another scheduled interview.",
            }

        schedule = InterviewSchedule.objects.create(
            interview=interview,
            availability=slot,
            scheduled_start=slot.start_time,
            scheduled_end=slot.end_time,
            status="SCHEDULED",
        )

        slot.is_available = False
        slot.save(
            update_fields=["is_available", "updated_at"]
        )

        interview.status = "SCHEDULED"
        interview.save(
            update_fields=["status", "updated_at"]
        )

        send_interview_scheduled_email(schedule)
        create_application_notification(
            interview.application,
            "INTERVIEW",
        )
        schedule.confirmation_sent = True
        schedule.save(update_fields=["confirmation_sent", "updated_at"])

        return {
            "success": True,
            "schedule": schedule,
        }

    def reschedule_interview(
        self,
        schedule,
        new_slot,
    ):
        """Move an existing interview to a new available slot."""

        is_valid, error = self.validate_slot(new_slot)

        if not is_valid:
            return {
                "success": False,
                "error": error,
            }

        if self.has_conflict(
            new_slot.start_time,
            new_slot.end_time,
            exclude_schedule=schedule,
        ):
            return {
                "success": False,
                "error": "The new interview slot conflicts with another scheduled interview.",
            }

        old_slot = schedule.availability

        if old_slot:
            old_slot.is_available = True
            old_slot.save(
                update_fields=["is_available", "updated_at"]
            )

        schedule.availability = new_slot
        schedule.scheduled_start = new_slot.start_time
        schedule.scheduled_end = new_slot.end_time
        schedule.status = "RESCHEDULED"
        schedule.confirmation_sent = False
        schedule.save()

        new_slot.is_available = False
        new_slot.save(
            update_fields=["is_available", "updated_at"]
        )

        send_interview_scheduled_email(schedule)
        create_application_notification(
            schedule.interview.application,
            "INTERVIEW",
        )
        schedule.confirmation_sent = True
        schedule.save(update_fields=["confirmation_sent", "updated_at"])

        return {
            "success": True,
            "schedule": schedule,
        }