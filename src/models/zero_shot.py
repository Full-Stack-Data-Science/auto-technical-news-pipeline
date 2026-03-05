from transformers import pipeline
from models.labels import BINARY_LABELS, LABEL_DEFINITIONS

from common.utils import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)

# -------- zero_shot ---------
from transformers import pipeline

binary_classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli"
)

multi_classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli"
)

def is_non_tech_zero_shot(
    text,
    tech_threshold=0.52
):
    """
    Strong bias toward Non-technical.
    Returns True if Non-technical, False if Technical.
    """
    result = binary_classifier(
        text,
        BINARY_LABELS,
        multi_label=False
    )
    scores = dict(zip(result["labels"], result["scores"]))
    tech_label, _ = BINARY_LABELS
    tech_score = scores.get(tech_label, 0.0)
    
    if tech_score < tech_threshold:
        return True

    return False

expanded_labels = list(LABEL_DEFINITIONS.keys())
def classify_zero_shot(text):
    result = multi_classifier(
        text,
        expanded_labels,
        multi_label=True
    )

    scores = {
        LABEL_DEFINITIONS[label]: score
        for label, score in zip(result["labels"], result["scores"])
    }

    return scores
