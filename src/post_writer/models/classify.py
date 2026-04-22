
from post_writer.models.rules import (
    is_empty,
    is_too_short,
    is_non_technical_rule_based,
    is_ops_mlops_rule_based
)
from post_writer.models.zero_shot import (
    is_non_tech_zero_shot,
    classify_zero_shot
)

from common.utils import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)

def classify_text(text, margin=0.06):
    logger.info("Post content classification: ")

    if is_empty(text) or is_too_short(text):
        logger.info(" --> Text is not long enough")
        return ["Non-technical"]

    if is_non_technical_rule_based(text):
        logger.info(" --> Classification technical rule bases")
        return ["Non-technical"]

    if is_non_tech_zero_shot(text):
        logger.info(" --> Binary classification by zero shot")
        return ["Non-technical"]
    res = []
    if (is_ops_mlops_rule_based(text)):
        logger.info(" --> MLOps rule bases")
        res.append("Orchestration")

    logger.info(" --> Zero shot tech classifcation")
    scores = classify_zero_shot(text)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    top_label, top_score = sorted_scores[0]
    second_label, second_score = (
        sorted_scores[1] if len(sorted_scores) > 1 else (None, 0.0)
    )

    res = [top_label]
    if second_label and abs(top_score - second_score) <= margin:
        res.append(second_label)

    return res