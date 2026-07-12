import unittest
from unittest.mock import MagicMock

from post_writer.post_classification.config import ClassificationConfig
from post_writer.post_classification.result import ClassificationResult
from post_writer.post_classification.rules import (
    is_empty,
    is_too_short,
    is_non_technical_rule_based,
    is_ops_mlops_rule_based,
)
from post_writer.post_classification.classifier import PostClassifier
from post_writer.post_classification import classify_text

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

LONG_NON_TECHNICAL = (
    "I visited my grandmother and we talked about the old days. "
    "She made delicious soup for lunch and we sat by the window watching the birds. "
    "It was a peaceful afternoon spent together reminiscing about childhood memories."
)

LONG_TECHNICAL = (
    "We fine-tuned a transformer-based LLM using supervised learning with RLHF. "
    "The model achieves strong benchmark results on NLP tasks including named entity recognition, "
    "text classification, and sequence labeling with improved precision and recall metrics."
)

LONG_MLOPS = (
    "We deployed our kubeflow pipeline to kubernetes for model serving with ci/cd monitoring "
    "using mlflow for experiment tracking and model registry. The deployment uses docker containers "
    "with autoscaling and latency in production infrastructure for high reliability."
)


def _classifier_with_mock_zs():
    """PostClassifier with a lazily-injected MagicMock zero-shot classifier."""
    clf = PostClassifier()
    mock_zs = MagicMock()
    clf._zero_shot = mock_zs
    return clf, mock_zs


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

class TestIsEmpty(unittest.TestCase):
    def test_none(self):
        self.assertTrue(is_empty(None))

    def test_empty_string(self):
        self.assertTrue(is_empty(""))

    def test_whitespace_only(self):
        self.assertTrue(is_empty("   "))

    def test_valid_text(self):
        self.assertFalse(is_empty("Some content"))


class TestIsTooShort(unittest.TestCase):
    def test_below_threshold(self):
        self.assertTrue(is_too_short("only four words here"))

    def test_at_threshold(self):
        words = " ".join(["word"] * 25)
        self.assertFalse(is_too_short(words, min_words=25))

    def test_above_threshold(self):
        words = " ".join(["word"] * 30)
        self.assertFalse(is_too_short(words))


class TestIsNonTechnicalRuleBased(unittest.TestCase):
    def test_empty_is_non_technical(self):
        self.assertTrue(is_non_technical_rule_based(""))

    def test_non_technical_text(self):
        # No technical keyword in this sentence
        self.assertTrue(is_non_technical_rule_based(
            "I visited my grandmother and we talked about the old days."
        ))

    def test_technical_keyword_present(self):
        # "deep learning" is in TECHNICAL_KEYWORDS
        self.assertFalse(is_non_technical_rule_based(
            "We trained a model using deep learning on image data."
        ))

    def test_llm_keyword(self):
        self.assertFalse(is_non_technical_rule_based(
            "The llm was fine-tuned on a custom dataset for generation."
        ))


class TestIsOpsMlopsRuleBased(unittest.TestCase):
    def test_empty_returns_false(self):
        self.assertFalse(is_ops_mlops_rule_based(""))

    def test_non_ops_text_returns_false(self):
        self.assertFalse(is_ops_mlops_rule_based(LONG_NON_TECHNICAL))

    def test_short_text_with_ops_verb_and_keyword(self):
        # < 50 words, ops verb "deploy" + keyword "kubernetes"
        self.assertTrue(is_ops_mlops_rule_based(
            "Deploy kubernetes model with monitoring."
        ))

    def test_high_ops_keyword_score(self):
        # mlops + mlflow + kubeflow → ops_score >= 3
        self.assertTrue(is_ops_mlops_rule_based(
            "We use mlops mlflow kubeflow for experiment tracking and model registry management."
        ))

    def test_ops_phrase_with_context(self):
        # phrase "model deployment" + context word "production"
        self.assertTrue(is_ops_mlops_rule_based(
            "The model deployment monitoring pipeline runs in production "
            "and provides latency and reliability metrics for our infrastructure."
        ))

    def test_long_ops_text(self):
        self.assertTrue(is_ops_mlops_rule_based(LONG_MLOPS))

# ---------------------------------------------------------------------------
# PostClassifier — exit stages
# ---------------------------------------------------------------------------

class TestPostClassifierPreFilter(unittest.TestCase):
    def setUp(self):
        self.clf, self.mock_zs = _classifier_with_mock_zs()

    def test_empty_text(self):
        result = self.clf.classify("")
        self.assertEqual(result.exit_stage, "pre_filter")
        self.assertFalse(result.is_technical)
        self.assertEqual(result.labels, ["Non-technical"])
        self.mock_zs.is_non_technical.assert_not_called()

    def test_too_short_text(self):
        result = self.clf.classify("Short text only.")
        self.assertEqual(result.exit_stage, "pre_filter")
        self.assertFalse(result.is_technical)
        self.mock_zs.is_non_technical.assert_not_called()

    def test_whitespace_only(self):
        result = self.clf.classify("     ")
        self.assertEqual(result.exit_stage, "pre_filter")
        self.assertFalse(result.is_technical)


class TestPostClassifierRuleBased(unittest.TestCase):
    def setUp(self):
        self.clf, self.mock_zs = _classifier_with_mock_zs()

    def test_long_non_technical_text_exits_rule_based(self):
        result = self.clf.classify(LONG_NON_TECHNICAL)
        self.assertEqual(result.exit_stage, "rule_based")
        self.assertFalse(result.is_technical)
        self.assertEqual(result.labels, ["Non-technical"])
        self.mock_zs.is_non_technical.assert_not_called()


class TestPostClassifierZeroShotBinary(unittest.TestCase):
    def setUp(self):
        self.clf, self.mock_zs = _classifier_with_mock_zs()

    def test_technical_text_rejected_by_binary_classifier(self):
        # Has technical keywords (passes rules), but zero-shot binary says non-technical
        self.mock_zs.is_non_technical.return_value = True

        result = self.clf.classify(LONG_TECHNICAL)
        self.assertEqual(result.exit_stage, "zero_shot_binary")
        self.assertFalse(result.is_technical)
        self.assertEqual(result.labels, ["Non-technical"])
        self.mock_zs.classify_topics.assert_not_called()


class TestPostClassifierZeroShotMulti(unittest.TestCase):
    def setUp(self):
        self.clf, self.mock_zs = _classifier_with_mock_zs()
        self.mock_zs.is_non_technical.return_value = False

    def test_single_label_when_scores_far_apart(self):
        self.mock_zs.classify_topics.return_value = {
            "Generative AI": 0.9,
            "NLP": 0.5,
            "Machine Learning": 0.3,
        }
        result = self.clf.classify(LONG_TECHNICAL)
        self.assertEqual(result.exit_stage, "zero_shot_multi")
        self.assertTrue(result.is_technical)
        self.assertEqual(result.labels, ["Generative AI"])

    def test_two_labels_when_scores_within_margin(self):
        # |0.80 - 0.76| = 0.04 <= default margin 0.06
        self.mock_zs.classify_topics.return_value = {
            "Generative AI": 0.80,
            "NLP": 0.76,
            "Machine Learning": 0.4,
        }
        result = self.clf.classify(LONG_TECHNICAL)
        self.assertTrue(result.is_technical)
        self.assertIn("Generative AI", result.labels)
        self.assertIn("NLP", result.labels)
        self.assertNotIn("Machine Learning", result.labels)

    def test_scores_clearly_within_margin_includes_second_label(self):
        # |0.80 - 0.75| = 0.05 < 0.06 margin → second label included
        self.mock_zs.classify_topics.return_value = {
            "Generative AI": 0.80,
            "NLP": 0.75,
        }
        result = self.clf.classify(LONG_TECHNICAL)
        self.assertIn("NLP", result.labels)

    def test_scores_just_beyond_margin(self):
        # |0.80 - 0.73| = 0.07 > 0.06 → second label excluded
        self.mock_zs.classify_topics.return_value = {
            "Generative AI": 0.80,
            "NLP": 0.73,
        }
        result = self.clf.classify(LONG_TECHNICAL)
        self.assertEqual(result.labels, ["Generative AI"])

    def test_orchestration_label_combined_with_zero_shot(self):
        # MLOps text should add "Orchestration" from rule, plus top zero-shot label
        self.mock_zs.classify_topics.return_value = {
            "Orchestration": 0.85,
            "Machine Learning": 0.4,
        }
        result = self.clf.classify(LONG_MLOPS)
        self.assertTrue(result.is_technical)
        self.assertIn("Orchestration", result.labels)

    def test_orchestration_not_duplicated(self):
        # Zero-shot also returns Orchestration as top — should appear only once
        self.mock_zs.classify_topics.return_value = {
            "Orchestration": 0.9,
            "Machine Learning": 0.3,
        }
        result = self.clf.classify(LONG_MLOPS)
        self.assertEqual(result.labels.count("Orchestration"), 1)

    def test_scores_populated_in_result(self):
        scores = {"Generative AI": 0.9, "NLP": 0.5}
        self.mock_zs.classify_topics.return_value = scores
        result = self.clf.classify(LONG_TECHNICAL)
        self.assertEqual(result.scores, scores)

    def test_custom_config_margin(self):
        cfg = ClassificationConfig(score_margin=0.0)  # only add second label when difference is 0
        clf = PostClassifier(config=cfg)
        mock_zs = MagicMock()
        mock_zs.is_non_technical.return_value = False
        mock_zs.classify_topics.return_value = {
            "Generative AI": 0.80,
            "NLP": 0.60,  # |0.80 - 0.60| = 0.2 > 0.0 → excluded
        }
        clf._zero_shot = mock_zs
        result = clf.classify(LONG_TECHNICAL)
        self.assertEqual(len(result.labels), 1)

    def test_custom_config_tech_threshold_propagated(self):
        # Verify config is wired through to ZeroShotClassifier
        cfg = ClassificationConfig(tech_threshold=0.9)
        clf = PostClassifier(config=cfg)
        self.assertIsNone(clf._zero_shot)  # not yet initialised
        zs = clf.zero_shot
        self.assertEqual(zs.config.tech_threshold, 0.9)


# ---------------------------------------------------------------------------
# PostClassifier — model lazy loading
# ---------------------------------------------------------------------------

class TestPostClassifierLazyLoading(unittest.TestCase):
    def test_zero_shot_not_loaded_on_init(self):
        clf = PostClassifier()
        self.assertIsNone(clf._zero_shot)

    def test_zero_shot_loaded_once_on_first_access(self):
        clf = PostClassifier()
        # Inject mock so we don't hit the real model
        mock_zs = MagicMock()
        clf._zero_shot = mock_zs
        # Access twice — same object returned
        self.assertIs(clf.zero_shot, mock_zs)
        self.assertIs(clf.zero_shot, mock_zs)


# ---------------------------------------------------------------------------
# classify_text convenience wrapper (public API)
# ---------------------------------------------------------------------------

class TestClassifyText(unittest.TestCase):
    def test_empty_input_returns_non_technical(self):
        labels = classify_text("")
        self.assertEqual(labels, ["Non-technical"])

    def test_too_short_returns_non_technical(self):
        labels = classify_text("Too short.")
        self.assertEqual(labels, ["Non-technical"])

    def test_returns_list(self):
        labels = classify_text("")
        self.assertIsInstance(labels, list)

    def test_non_technical_long_text_no_model(self):
        # Rule-based rejection — no model needed
        labels = classify_text(LONG_NON_TECHNICAL)
        self.assertEqual(labels, ["Non-technical"])


if __name__ == "__main__":
    unittest.main()
