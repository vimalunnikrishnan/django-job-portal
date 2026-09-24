def check_candidate_eligibility(
    match_percentage,
    shortlist_threshold=70,
):
    if match_percentage >= shortlist_threshold:
        return {
            "eligible": True,
            "action": "SHORTLIST",
            "reason": (
                f"Match percentage {match_percentage}% "
                f"is above the shortlist threshold of "
                f"{shortlist_threshold}%."
            ),
        }

    return {
        "eligible": False,
        "action": "REJECT",
        "reason": (
            f"Match percentage {match_percentage}% "
            f"is below the shortlist threshold of "
            f"{shortlist_threshold}%."
        ),
    }