from django.utils import timezone

from jobs.services.ai_interview_service import create_ai_interview
from jobs.tasks import start_ai_interview_task

from accounts.services.ai_call_eligibility import (
    check_ai_call_eligibility,
)
from accounts.services.ai_call_scheduler import (
    get_next_ai_call_time,
)


def trigger_ai_call(
    application,
    match_percentage,
    shortlist_threshold=70,
):
    job = application.job
    candidate_profile = application.candidate.candidate_profile

    eligibility = check_ai_call_eligibility(
        match_percentage=match_percentage,
        shortlist_threshold=shortlist_threshold,
        job_status=job.status,
        job_is_active=job.is_active,
        candidate_available=candidate_profile.is_available_for_ai_interview,
    )

    if not eligibility["eligible"]:
        return {
            "triggered": False,
            "eligibility": eligibility,
        }

    interview, created = create_ai_interview(application)

    if not created:
        return {
            "triggered": False,
            "eligibility": eligibility,
            "interview_id": interview.id,
            "message": "AI interview already exists.",
        }

    scheduled_time = get_next_ai_call_time(timezone.now())

    task = start_ai_interview_task.apply_async(
        args=[interview.id],
        eta=scheduled_time,
    )

    return {
        "triggered": True,
        "eligibility": eligibility,
        "interview_id": interview.id,
        "task_id": task.id,
        "scheduled_time": scheduled_time,
    }