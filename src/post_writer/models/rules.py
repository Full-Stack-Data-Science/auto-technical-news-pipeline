import re
from post_writer.models.keywords import *

from common.utils import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)

def is_ops_mlops_rule_based(text):
    """
    Rule-based filter to identify Ops / MLOps / LLMOps / AgentOps content.
    Returns True if post is about operations, infrastructure, deployment,
    CI/CD, debugging, monitoring, or production systems.
    """    
    if not isinstance(text, str) or not text.strip():
        return False

    text_lower = text.lower()

   
    ops_score = sum(1 for kw in ops_keywords if kw in text_lower)

    # --------------------------------------------------
    # Ops / deployment / CI phrases
    # --------------------------------------------------
    ops_phrases = [
        r'\b(deploy|debug|investigate|fix|analyze)\b.*\b(ci|pipeline|workflow|build)\b',
        r'\b(ci|pipeline|workflow)\b.*\b(fail|failure|broken|stuck)\b',
        r'\b(deploy(ing|ed|ment)?|serving|host(ing)?)\s+(model|ml|llm|agent)\b',
        r'\b(model|llm|agent)\s+(deployment|serving|monitoring|pipeline)\b',
        r'\b(container(ize|ized)?|docker(ize|ized)?)\b',
        r'\b(orchestrat(e|ing|ion)|automat(e|ing|ion))\b',
        r'\b(kubernetes|k8s)\b',
        r'\b(prompt|token|inference)\s+(cost|usage|monitoring|caching)\b',
        r'\b(agent)\s+(orchestration|deployment|monitoring|workflow)\b',
        r'\b(langchain|langgraph|autogen|crewai)\b.*\b(deploy|production)\b'
    ]

    phrase_matches = sum(1 for p in ops_phrases if re.search(p, text_lower))

    # --------------------------------------------------
    # Short imperative ops tasks (important for X)
    # --------------------------------------------------
    ops_verbs = [
        'debug', 'deploy', 'monitor', 'fix', 'investigate',
        'analyze', 'scale', 'configure', 'optimize'
    ]

    if len(text.split()) < 50:
        if any(v in text_lower for v in ops_verbs) and ops_score >= 1:
            return True

    # --------------------------------------------------
    # Strong indicators
    # --------------------------------------------------
    if ops_score >= 3 or phrase_matches >= 2:
        return True

    # Medium indicators + operational context
    if ops_score >= 2 or phrase_matches >= 1:
        operational_context = [
            'production', 'pipeline', 'infrastructure',
            'latency', 'performance', 'availability',
            'reliability', 'scale'
        ]

        context_score = sum(1 for k in operational_context if k in text_lower)
        if context_score >= 1:
            return True

    return False


def is_non_technical_rule_based(text):
    """
    Returns True if post is clearly non-technical.
    Conservative filter: only returns False if strong technical evidence exists.
    """
    if not isinstance(text, str) or not text.strip():
        return True

    text_lower = text.lower()

    if any(kw in text_lower for kw in TECHNICAL_KEYWORDS):
        return False

    return True

def is_empty(text):
    return not isinstance(text, str) or not text.strip()

def is_too_short(text, min_words=25):
    return len(text.split()) < min_words