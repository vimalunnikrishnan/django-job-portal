from django.test import SimpleTestCase

from jobs.services.ai_answer_evaluation.scoring import (
    AnswerScoringEngine,
)


class AnswerScoringEngineTests(SimpleTestCase):

    def setUp(self):
        self.engine = AnswerScoringEngine()

    def test_normalize_text(self):
        result = self.engine.normalize_text(
            "Python, Django & REST!"
        )

        self.assertEqual(
            result,
            "python  django   rest ",
        )

    def test_extract_keywords(self):
        result = self.engine.extract_keywords(
            "I have Python and Django experience."
        )

        self.assertEqual(
            result,
            {"have", "python", "django", "experience."},
        )

    def test_calculate_relevance(self):
        result = self.engine.calculate_relevance(
            "Python Django developer",
            "I am a Python Django developer",
        )

        self.assertEqual(result, 100)

    def test_calculate_completeness(self):
        self.assertEqual(
            self.engine.calculate_completeness("Python"),
            25,
        )

        self.assertEqual(
            self.engine.calculate_completeness(
                "Python Django developer with experience"
            ),
            50,
        )

    def test_calculate_keyword_score(self):
        result = self.engine.calculate_keyword_score(
            "I know Python and Django",
            ["python", "django"],
        )

        self.assertEqual(result, 100)

    def test_calculate_overall_score(self):
        result = self.engine.calculate_overall_score(
            100,
            100,
            100,
        )

        self.assertEqual(result, 100)

    def test_evaluate_returns_expected_keys(self):
        result = self.engine.evaluate(
            question="Explain Python Django",
            answer="I have Python Django development experience",
            expected_keywords=["python", "django"],
        )

        self.assertEqual(
            set(result.keys()),
            {
                "relevance_score",
                "completeness_score",
                "keyword_score",
                "overall_score",
                "confidence",
                "ai_annotations",
            },
        )

        self.assertEqual(
            result["ai_annotations"]["evaluation_method"],
            "rule_based",
        )