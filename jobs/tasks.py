from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

@shared_task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)

def start_ai_interview_task(self, interview_id):
    """
    Background task to start AI interview processing.
    """

    from jobs.models import AIInterview

    try:
        interview = AIInterview.objects.get(id=interview_id)
    except ObjectDoesNotExist:
        return {
            "interview_id": interview_id,
            "status": "FAILED",
            "message": "AI interview not found.",
        }

    if interview.status != "PENDING":
        return {
            "interview_id": interview.id,
            "status": interview.status,
            "message": "Interview is not in PENDING state.",
        }

    interview.status = "SCHEDULED"
    interview.save(update_fields=["status", "updated_at"])

    return {
        "interview_id": interview.id,
        "status": interview.status,
        "message": "AI interview scheduled for background processing.",
    }