from accounts.services.auto_shortlisting import auto_process_application
from jobs.models import Application


def auto_process_applications(
    shortlist_threshold=70,
):
    applications = (
        Application.objects
        .filter(status="APPLIED")
        .select_related(
            "candidate",
            "candidate__candidate_profile",
            "job",
        )
    )

    results = []

    for application in applications:
        try:
            result = auto_process_application(
                application,
                shortlist_threshold=shortlist_threshold,
            )
            results.append(result)

        except Exception as exc:
            results.append(
                {
                    "application": application,
                    "success": False,
                    "error": str(exc),
                }
            )

    return results