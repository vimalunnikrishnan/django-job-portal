from accounts.models import CandidateProfile
from accounts.services.ats_scoring import calculate_and_save_ats_score
from jobs.models import Application


def rank_candidates_for_job(job):
    applications = (
        Application.objects
        .filter(job=job)
        .select_related("candidate")
    )

    ranked_candidates = []

    for application in applications:
        try:
            candidate_profile = CandidateProfile.objects.get(
                user=application.candidate,
                is_deleted=False,
            )
        except CandidateProfile.DoesNotExist:
            continue

        ats_score = calculate_and_save_ats_score(
            job,
            candidate_profile,
        )

        ranked_candidates.append(
            {
                "candidate": candidate_profile,
                "application": application,
                "ats_score": ats_score,
            }
        )

    ranked_candidates.sort(
        key=lambda item: item["ats_score"].match_percentage,
        reverse=True,
    )

    return ranked_candidates