from jobs.models import Application, ATSScore, AIInterview


class CandidateReportService:
    """Generate a structured candidate evaluation report."""

    @staticmethod
    def generate_report(application_id, employer):
        """
        Generate a report only when the application belongs
        to a job owned by the requesting employer.
        """

        application = (
            Application.objects
            .select_related(
                "candidate",
                "job",
                "job__employer",
            )
            .filter(
                pk=application_id,
                job__employer=employer,
            )
            .first()
        )

        if application is None:
            return None

        candidate = application.candidate
        job = application.job

        # Candidate profile information
        profile = getattr(candidate, "candidate_profile", None)

        candidate_details = {
            "id": candidate.id,
            "name": candidate.get_full_name() or candidate.username,
            "email": candidate.email,
            "skills": profile.skills if profile else "",
            "education": profile.education if profile else "",
            "experience_years": profile.experience if profile else 0,
        }

        # ATS evaluation
        ats = ATSScore.objects.filter(
            candidate__user=candidate,
            job=job,
        ).first()

        ats_report = None

        if ats:
            ats_report = {
                "skill_score": ats.skill_score,
                "experience_score": ats.experience_score,
                "education_score": ats.education_score,
                "match_percentage": ats.match_percentage,
                "updated_at": ats.updated_at.isoformat(),
            }

        # AI interview evaluation
        interview = (
            AIInterview.objects
            .filter(application=application)
            .first()
        )

        interview_report = None
        answer_reports = []
        strengths = []
        potential_risks = []

        if interview:
            interview_report = {
                "id": interview.id,
                "status": interview.status,
                "final_score": interview.final_score,
                "started_at": (
                    interview.started_at.isoformat()
                    if interview.started_at else None
                ),
                "completed_at": (
                    interview.completed_at.isoformat()
                    if interview.completed_at else None
                ),
            }

            answers = (
                interview.sessions
                .prefetch_related(
                    "questions__answer__evaluation"
                )
                .all()
            )

            for session in answers:
                for question in session.questions.all():
                    answer = getattr(question, "answer", None)

                    if answer is None:
                        continue

                    evaluation = getattr(answer, "evaluation", None)

                    answer_report = {
                        "session_id": session.session_id,
                        "question": question.question,
                        "answer": answer.answer_text,
                        "transcript": answer.transcript,
                        "evaluation": None,
                    }

                    if evaluation:
                        annotations = evaluation.ai_annotations or {}

                        answer_report["evaluation"] = {
                            "relevance_score": evaluation.relevance_score,
                            "completeness_score": (
                                evaluation.completeness_score
                            ),
                            "keyword_score": evaluation.keyword_score,
                            "overall_score": evaluation.overall_score,
                            "confidence": evaluation.confidence,
                            "feedback": evaluation.feedback,
                            "annotations": annotations,
                        }

                        if evaluation.overall_score >= 75:
                            strengths.append({
                                "question": question.question,
                                "evidence": (
                                    "Strong answer evaluation"
                                ),
                                "score": evaluation.overall_score,
                            })

                        if evaluation.overall_score < 50:
                            potential_risks.append({
                                "question": question.question,
                                "evidence": (
                                    "Low answer evaluation score"
                                ),
                                "score": evaluation.overall_score,
                            })

                        missing_keywords = annotations.get(
                            "missing_keywords", []
                        )

                        if missing_keywords:
                            potential_risks.append({
                                "question": question.question,
                                "evidence": (
                                    "Keywords not identified in the answer"
                                ),
                                "missing_keywords": missing_keywords,
                            })

                    answer_reports.append(answer_report)

        # Explainable candidate evaluation summary
        ats_match = (
            ats.match_percentage
            if ats is not None
            else None
        )

        interview_score = (
            interview.final_score
            if interview is not None
            else None
        )

        evaluation_summary = {
            "ats_match_percentage": ats_match,
            "interview_score": interview_score,
            "ats_available": ats_match is not None,
            "interview_score_available": interview_score is not None,
            "recommendation_basis": [],
            "assessment_note": (
                "These indicators summarize recorded evaluation data. "
                "They do not guarantee hiring success and must be reviewed "
                "alongside the candidate's qualifications and interview."
            ),
        }

        if ats_match is not None:
            evaluation_summary["recommendation_basis"].append(
                "ATS match percentage is available."
            )

        if interview_score is not None:
            evaluation_summary["recommendation_basis"].append(
                "AI interview score is available."
            )

        return {
            "report_version": "1.0",
            "application": {
                "id": application.id,
                "status": application.status,
                "applied_at": application.applied_at.isoformat(),
            },
            "candidate": candidate_details,
            "job": {
                "id": job.id,
                "title": job.title,
                "employer_id": job.employer_id,
            },
            "ats_evaluation": ats_report,
            "interview_evaluation": interview_report,
            "evaluation_summary": evaluation_summary,
            "answer_evaluations": answer_reports,
            "summary": {
                "answers_evaluated": sum(
                    1 for item in answer_reports
                    if item["evaluation"] is not None
                ),
                "strengths": strengths,
                "potential_risks": potential_risks,
                "assessment_note": (
                    "This report summarizes recorded evaluation data. "
                    "Potential risks require recruiter review and should "
                    "not be treated as definitive conclusions."
                ),
            },
        }