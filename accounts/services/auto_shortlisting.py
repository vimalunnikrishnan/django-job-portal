from accounts.services.notification_service import (
    create_application_notification,
)
from accounts.services.ats_scoring import calculate_and_save_ats_score
from accounts.services.eligibility import check_candidate_eligibility


def auto_process_application(
    application,
    shortlist_threshold=70,
):
    candidate_profile = application.candidate.candidate_profile

    ats_score = calculate_and_save_ats_score(
        application.job,
        candidate_profile,
    )

    eligibility = check_candidate_eligibility(
        ats_score.match_percentage,
        shortlist_threshold=shortlist_threshold,
    )

    if eligibility["action"] == "SHORTLIST":
        application.status = "SHORTLISTED"

        create_application_notification(
            application,
            "SHORTLISTED",
        )

    elif eligibility["action"] == "REJECT":
        application.status = "REJECTED"

        create_application_notification(
            application,
            "REJECTED",
        )

    application.save(update_fields=["status", "updated_at"])

    return {
        "application": application,
        "ats_score": ats_score,
        "eligibility": eligibility,
    }