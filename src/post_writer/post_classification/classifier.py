import logging

from common.utils import setup_logging
from post_writer.post_classification.config import ClassificationConfig
from post_writer.post_classification.result import ClassificationResult
from post_writer.post_classification.rules import (
    is_empty,
    is_too_short,
    is_non_technical_rule_based,
    is_ops_mlops_rule_based,
)
from post_writer.post_classification.zero_shot import ZeroShotClassifier

setup_logging()
logger = logging.getLogger(__name__)


class PostClassifier:
    """
    Two-stage classifier: cheap rule-based pre-filters, then zero-shot inference.

    Instantiate once and reuse — the underlying model is loaded lazily on first
    call and shared across both the binary and multi-label passes.
    """

    def __init__(self, config: ClassificationConfig = None):
        self.config = config or ClassificationConfig()
        self._zero_shot: ZeroShotClassifier | None = None

    @property
    def zero_shot(self) -> ZeroShotClassifier:
        if self._zero_shot is None:
            self._zero_shot = ZeroShotClassifier(self.config)
        return self._zero_shot

    def classify(self, text: str) -> ClassificationResult:
        logger.info("Classifying post content")

        if is_empty(text) or is_too_short(text, self.config.min_words):
            logger.info(" --> Rejected by pre-filter (empty / too short)")
            return ClassificationResult(
                labels=["Non-technical"],
                is_technical=False,
                exit_stage="pre_filter",
            )

        if is_non_technical_rule_based(text):
            logger.info(" --> Rejected by keyword rule filter")
            return ClassificationResult(
                labels=["Non-technical"],
                is_technical=False,
                exit_stage="rule_based",
            )

        if self.zero_shot.is_non_technical(text):
            logger.info(" --> Rejected by zero-shot binary classifier")
            return ClassificationResult(
                labels=["Non-technical"],
                is_technical=False,
                exit_stage="zero_shot_binary",
            )

        labels = []
        if is_ops_mlops_rule_based(text):
            logger.info(" --> MLOps/Ops rule matched")
            labels.append("Orchestration")

        scores = self.zero_shot.classify_topics(text)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        top_label, top_score = sorted_scores[0]
        if top_label not in labels:
            labels.append(top_label)

        if len(sorted_scores) > 1:
            second_label, second_score = sorted_scores[1]
            if abs(top_score - second_score) <= self.config.score_margin and second_label not in labels:
                labels.append(second_label)

        logger.info(" --> Zero-shot multi-label result: %s", labels)
        return ClassificationResult(
            labels=labels,
            is_technical=True,
            exit_stage="zero_shot_multi",
            scores=scores,
        )
