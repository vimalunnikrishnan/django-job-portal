from accounts.models import CandidateProfile
from accounts.services.resume_parser import extract_resume_text
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.conf import settings
from jobs.services.ai_bridge.service import AIBridgeService
from jobs.models import CallLog

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

    bridge = AIBridgeService()

    call_result = bridge.make_call(
        phone_number="+910000000000",
        voice="female",
        language="en",
    )

    if not call_result["success"]:
        interview.status = "FAILED"
        interview.save(update_fields=["status", "updated_at"])

        return {
            "interview_id": interview.id,
            "status": "FAILED",
            "message": call_result["error"],
        }

    interview.call_id = call_result["call_id"]
    interview.save(update_fields=["call_id", "updated_at"])

    CallLog.objects.create(
        interview=interview,
        event="STARTED",
        reason="AI voice call queued successfully.",
        details={
            "provider": "mock",
            "call_id": call_result["call_id"],
            "voice": "female",
            "language": "en",
        },
    )

    return {
        "interview_id": interview.id,
        "status": interview.status,
        "call_id": interview.call_id,
        "message": "AI interview scheduled and voice call queued.",
    }


@shared_task
def send_email_task(subject, message, recipient):
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
    )

    return {
        "status": "SENT",
        "recipient": recipient,
        "subject": subject,
    }


@shared_task
def parse_resume_task(candidate_profile_id):
    try:
        profile = CandidateProfile.objects.get(id=candidate_profile_id)
    except CandidateProfile.DoesNotExist:
        return {
            "status": "FAILED",
            "message": "Candidate profile not found.",
        }

    if not profile.resume:
        return {
            "status": "FAILED",
            "message": "Candidate does not have a resume.",
        }

    try:
        with profile.resume.open("rb") as resume_file:
            text = extract_resume_text(resume_file)

        return {
            "status": "PARSED",
            "candidate_profile_id": profile.id,
            "characters": len(text),
        }

    except Exception as exc:
        return {
            "status": "FAILED",
            "candidate_profile_id": profile.id,
            "message": str(exc),
        }


@shared_task
def daily_maintenance_task():
    return {
        "status": "SUCCESS",
        "message": "Daily maintenance task executed.",
    }