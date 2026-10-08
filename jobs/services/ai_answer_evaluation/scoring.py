import re


class AnswerScoringEngine:

    RELEVANCE_WEIGHT = 0.40
    COMPLETENESS_WEIGHT = 0.30
    KEYWORD_WEIGHT = 0.30

    STOP_WORDS = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "am",
        "i",
        "my",
        "me",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "for",
        "with",
        "do",
        "you",
        "your",
        "what",
        "how",
        "many",
        "years",
    }

    def normalize_text(self, text):
        """Normalize text for scoring."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9+#.\s]", " ", text)
        return text

    def extract_keywords(self, text):
        """Extract meaningful keywords from text."""
        normalized = self.normalize_text(text)

        words = normalized.split()

        return {
            word
            for word in words
            if word not in self.STOP_WORDS and len(word) > 2
        }

    def calculate_relevance(self, question, answer):
        """Calculate how relevant the answer is to the question."""

        question_keywords = self.extract_keywords(question)
        answer_keywords = self.extract_keywords(answer)

        if not question_keywords:
            return 0

        matched = question_keywords.intersection(answer_keywords)

        score = (len(matched) / len(question_keywords)) * 100

        return min(round(score, 2), 100)

    def calculate_completeness(self, answer):
        """Calculate completeness based on answer length."""

        word_count = len(answer.split())

        if word_count == 0:
            return 0

        if word_count < 5:
            return 25

        if word_count < 10:
            return 50

        if word_count < 20:
            return 75

        return 100

    def calculate_keyword_score(self, answer, expected_keywords):
        """Calculate keyword matching score."""

        if not expected_keywords:
            return 0

        answer_keywords = self.extract_keywords(answer)

        expected = {
            keyword.lower().strip()
            for keyword in expected_keywords
        }

        matched = answer_keywords.intersection(expected)

        score = (len(matched) / len(expected)) * 100

        return min(round(score, 2), 100)

    def calculate_overall_score(
        self,
        relevance_score,
        completeness_score,
        keyword_score,
    ):
        """Calculate normalized weighted overall score."""

        score = (
            relevance_score * self.RELEVANCE_WEIGHT
            + completeness_score * self.COMPLETENESS_WEIGHT
            + keyword_score * self.KEYWORD_WEIGHT
        )

        return round(score, 2)

    def evaluate(
        self,
        question,
        answer,
        expected_keywords=None,
    ):
        """Evaluate an answer using all scoring dimensions."""

        expected_keywords = expected_keywords or []

        relevance_score = self.calculate_relevance(
            question,
            answer,
        )

        completeness_score = self.calculate_completeness(
            answer,
        )

        keyword_score = self.calculate_keyword_score(
            answer,
            expected_keywords,
        )

        overall_score = self.calculate_overall_score(
            relevance_score,
            completeness_score,
            keyword_score,
        )

        answer_length = len(answer.split())

        confidence = min(
            100,
            round(
                (completeness_score + relevance_score) / 2,
                2,
            ),
        )

        answer_keywords = self.extract_keywords(answer)

        expected = {
            keyword.lower().strip()
            for keyword in expected_keywords
        }

        matched_keywords = sorted(
            answer_keywords.intersection(expected)
        )

        missing_keywords = sorted(
            expected.difference(answer_keywords)
        )

        return {
            "relevance_score": relevance_score,
            "completeness_score": completeness_score,
            "keyword_score": keyword_score,
            "overall_score": overall_score,
            "confidence": confidence,
            "ai_annotations": {
                "answer_length": answer_length,
                "matched_keywords": matched_keywords,
                "missing_keywords": missing_keywords,
                "evaluation_method": "rule_based",
            },
        }