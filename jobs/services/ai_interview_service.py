from django.utils import timezone
from django.db import transaction

from jobs.models import AIInterview, AIInterviewQuestion


@transaction.atomic
def create_ai_interview(application):
    """
    Create one AI interview for an application.
    """

    interview, created = AIInterview.objects.get_or_create(
        application=application,
        defaults={
            "status": "PENDING",
        },
    )

    return interview, created


def add_interview_question(interview, question_text):
    """
    Add the next question to an AI interview.
    """

    next_sequence = (
        interview.questions.order_by("-sequence_number")
        .values_list("sequence_number", flat=True)
        .first()
        or 0
    ) + 1

    return AIInterviewQuestion.objects.create(
        interview=interview,
        question=question_text,
        sequence_number=next_sequence,
    )


def record_interview_answer(
    question,
    answer,
    transcript="",
    score=None,
    feedback="",
):
    """
    Record a candidate's answer and AI evaluation.
    """

    question.answer = answer
    question.transcript = transcript
    question.score = score
    question.feedback = feedback

    question.save(
        update_fields=[
            "answer",
            "transcript",
            "score",
            "feedback",
        ]
    )

    return question


def complete_ai_interview(interview):
    """
    Complete an AI interview and calculate the final score.
    """

    scores = list(
        interview.questions
        .exclude(score__isnull=True)
        .values_list("score", flat=True)
    )

    if not scores:
        raise ValueError("Cannot complete interview without scored questions.")

    final_score = sum(scores) / len(scores)

    interview.status = "COMPLETED"
    interview.final_score = round(final_score, 2)
    interview.completed_at = timezone.now()

    interview.save(
        update_fields=[
            "status",
            "final_score",
            "completed_at",
            "updated_at",
        ]
    )

    return interview