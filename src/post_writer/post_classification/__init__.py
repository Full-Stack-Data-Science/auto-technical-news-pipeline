from post_writer.post_classification.classifier import PostClassifier
from post_writer.post_classification.config import ClassificationConfig
from post_writer.post_classification.result import ClassificationResult

_default_classifier: PostClassifier | None = None


def classify_text(text: str) -> list:
    """Convenience wrapper around PostClassifier; returns label list."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = PostClassifier()
    return _default_classifier.classify(text).labels
