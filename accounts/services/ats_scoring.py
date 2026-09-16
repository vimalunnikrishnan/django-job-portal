
from jobs.models import ATSScore
def normalize_skills(skills_text):
    """
    Convert comma-separated skills into a normalized list.
    """

    if not skills_text:
        return []

    skills = skills_text.split(",")

    return [
        skill.strip().lower()
        for skill in skills
        if skill.strip()
    ]


def calculate_skill_score(job_skills, candidate_skills):
    """
    Calculate the percentage of required job skills
    matched by the candidate.
    """

    required_skills = normalize_skills(job_skills)
    candidate_skill_list = normalize_skills(candidate_skills)

    if not required_skills:
        return 0

    matched_skills = []

    for skill in required_skills:

        if skill in candidate_skill_list:
            matched_skills.append(skill)

    score = (
        len(matched_skills)
        / len(required_skills)
    ) * 100

    return round(score, 2)


def calculate_experience_score(
    required_experience,
    candidate_experience,
):
    """
    Calculate the experience match percentage.
    """

    if required_experience <= 0:
        return 100

    if candidate_experience >= required_experience:
        return 100

    score = (
        candidate_experience
        / required_experience
    ) * 100

    return round(score, 2)


def calculate_education_score(
    required_education,
    candidate_education,
):
    """
    Calculate the education relevance percentage.
    """

    if not required_education:
        return 100

    if not candidate_education:
        return 0

    required_list = [
        education.strip().lower()
        for education in required_education
        if education.strip()
    ]

    candidate_education_normalized = (
        candidate_education.strip().lower()
    )

    if candidate_education_normalized in required_list:
        return 100

    return 0


def calculate_ats_score(
    skill_score,
    experience_score,
    education_score,
):
    """
    Calculate the overall ATS score using weighted components.
    """

    skill_weight = 0.60
    experience_weight = 0.25
    education_weight = 0.15

    ats_score = (
        skill_score * skill_weight
        + experience_score * experience_weight
        + education_score * education_weight
    )

    return round(ats_score, 2)


def calculate_candidate_job_match(job, candidate):
    """
    Calculate the ATS match score between a job and a candidate.
    """

    skill_score = calculate_skill_score(
        job.skills,
        candidate.skills,
    )

    experience_score = calculate_experience_score(
        job.experience,
        candidate.experience,
    )

    education_score = calculate_education_score(
        [],
        candidate.education,
    )

    ats_score = calculate_ats_score(
        skill_score,
        experience_score,
        education_score,
    )

    return {
        "skill_score": skill_score,
        "experience_score": experience_score,
        "education_score": education_score,
        "match_percentage": ats_score,
    }


def calculate_and_save_ats_score(job, candidate):
    """
    Calculate the ATS score and store it in the database.
    """

    scores = calculate_candidate_job_match(
        job,
        candidate,
    )

    ats_score, created = ATSScore.objects.update_or_create(
        job=job,
        candidate=candidate,
        defaults={
            "skill_score": scores["skill_score"],
            "experience_score": scores["experience_score"],
            "education_score": scores["education_score"],
            "match_percentage": scores["match_percentage"],
        },
    )

    return ats_score