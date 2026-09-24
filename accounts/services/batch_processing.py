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
            "job",
        )
    )

    results = []

    for application in applications:
        result = auto_process_application(
            application,
            shortlist_threshold=shortlist_threshold,
        )

        results.append(result)

    return results