from accounts.services.ats_scoring import calculate_and_save_ats_score
from jobs.models import Application


def rank_candidates_for_job(job):
    applications = (
        Application.objects
        .filter(
            job=job,
            candidate__candidate_profile__is_deleted=False,
        )
        .select_related(
            "candidate",
            "candidate__candidate_profile",
        )
    )

    ranked_candidates = []

    for application in applications:
        candidate_profile = application.candidate.candidate_profile

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