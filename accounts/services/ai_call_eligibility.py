def check_ai_call_eligibility(
    match_percentage,
    shortlist_threshold,
    job_status,
    job_is_active,
    candidate_available,
):
    if match_percentage < shortlist_threshold:
        return {
            "eligible": False,
            "reason": "ATS score is below the shortlist threshold.",
        }

    if job_status != "OPEN":
        return {
            "eligible": False,
            "reason": "Job is not open.",
        }

    if not job_is_active:
        return {
            "eligible": False,
            "reason": "Job is inactive.",
        }

    if not candidate_available:
        return {
            "eligible": False,
            "reason": "Candidate is not available for an AI interview.",
        }

    return {
        "eligible": True,
        "reason": "Candidate is eligible for an AI interview.",
    }