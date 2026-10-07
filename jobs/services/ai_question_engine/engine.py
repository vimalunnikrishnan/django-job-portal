from django.utils import timezone

from jobs.models import (
    AIInterviewSession,
    AIAnswer,
    AIQuestion,
    JobQuestionMapping,
)


class AIQuestionEngine:

    def __init__(self, session):
        self.session = session

    def get_question_set(self):
        """Return active questions configured for the interview job."""
        job = self.session.interview.application.job

        return (
            JobQuestionMapping.objects.filter(
                job=job,
                is_active=True,
                question_template__is_active=True,
            )
            .select_related(
                "question_template",
                "question_template__follow_up_question",
            )
            .order_by("order")
        )

    def get_next_question(self):
        """Create and return the next question for the interview session."""

        current_mapping = self.get_current_question()

        if current_mapping is None:
            return None

        return self.create_question(
            current_mapping.question_template
        )

    def create_question(self, question_template):
        """Create an AIQuestion and update session state."""

        last_question = (
            AIQuestion.objects.filter(
                session=self.session
            )
            .order_by("-sequence_number")
            .first()
        )

        next_sequence = (
            last_question.sequence_number + 1
            if last_question
            else 1
        )

        question = AIQuestion.objects.create(
            session=self.session,
            question_template=question_template,
            question=question_template.question,
            sequence_number=next_sequence,
        )

        return question

    def get_current_question(self):
        """Return the question at the current session index."""

        mappings = list(self.get_question_set())

        index = self.session.current_question_index

        if index >= len(mappings):
            return None

        return mappings[index]

    def get_follow_up_question(self, question):
        """Return the configured follow-up question."""
        if not question.question_template:
            return None

        return question.question_template.follow_up_question

    def should_ask_follow_up(self, question, answer_text):
        """Determine whether a follow-up question should be asked."""

        follow_up = self.get_follow_up_question(question)

        if not follow_up:
            return False

        normalized_answer = answer_text.strip().lower()

        positive_answers = {
            "yes",
            "yeah",
            "yep",
            "sure",
            "absolutely",
            "i do",
            "i have",
        }

        return normalized_answer in positive_answers

    def advance_question_index(self):
        """Move the interview session to the next question."""
        self.session.current_question_index += 1
        self.session.save(
            update_fields=["current_question_index", "updated_at"]
        )

        return self.session.current_question_index

    def save_answer(self, question, answer_text):
        """Store the candidate's answer for the current question."""

        answer, created = AIAnswer.objects.update_or_create(
            question=question,
            defaults={
                "answer_text": answer_text,
                "answered_at": timezone.now(),
            },
        )

        return answer

    def process_answer(self, question, answer_text):
        """Process an answer and determine the next question."""

        self.save_answer(question, answer_text)

        should_follow_up = self.should_ask_follow_up(
            question,
            answer_text,
        )

        if should_follow_up:
            follow_up = self.get_follow_up_question(question)

            if follow_up:
                return {
                    "action": "FOLLOW_UP",
                    "question_template": follow_up,
                    "question": follow_up.question,
                }

        self.advance_question_index()

        next_mapping = self.get_current_question()

        if next_mapping is None:
            return {
                "action": "COMPLETE",
                "question_template": None,
                "question": None,
            }

        return {
            "action": "NEXT",
            "question_template": next_mapping.question_template,
            "question": next_mapping.question_template.question,
        }

    def is_interview_complete(self):
        """Return True when all configured questions are completed."""
        return self.get_current_question() is None