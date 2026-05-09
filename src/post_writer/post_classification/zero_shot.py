from post_writer.post_classification.labels import BINARY_LABELS, LABEL_DEFINITIONS
from post_writer.post_classification.config import ClassificationConfig


class ZeroShotClassifier:
    """Wraps a single HuggingFace zero-shot pipeline with lazy initialisation."""

    def __init__(self, config: ClassificationConfig):
        self.config = config
        self._pipeline = None

    @property
    def pipeline(self):
        if self._pipeline is None:
            from transformers import pipeline as hf_pipeline
            self._pipeline = hf_pipeline(
                "zero-shot-classification",
                model=self.config.model_name,
            )
        return self._pipeline

    def is_non_technical(self, text: str) -> bool:
        """Binary pass: returns True when the post is non-technical."""
        result = self.pipeline(text, BINARY_LABELS, multi_label=False)
        scores = dict(zip(result["labels"], result["scores"]))
        tech_label = BINARY_LABELS[0]
        return scores.get(tech_label, 0.0) < self.config.tech_threshold

    def classify_topics(self, text: str) -> dict:
        """Multi-label pass: returns {topic_name: score} for all known labels."""
        expanded_labels = list(LABEL_DEFINITIONS.keys())
        result = self.pipeline(text, expanded_labels, multi_label=True)
        return {
            LABEL_DEFINITIONS[label]: score
            for label, score in zip(result["labels"], result["scores"])
        }
