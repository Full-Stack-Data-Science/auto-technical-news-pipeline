import re
from post_writer.post_classification.keywords import TECHNICAL_KEYWORDS, OPS_KEYWORDS


def is_empty(text: str) -> bool:
    return not isinstance(text, str) or not text.strip()


def is_too_short(text: str, min_words: int = 25) -> bool:
    return len(text.split()) < min_words


def is_non_technical_rule_based(text: str) -> bool:
    """Returns True if no technical keyword is found — conservative fast-reject."""
    if not isinstance(text, str) or not text.strip():
        return True
    text_lower = text.lower()
    return not any(kw in text_lower for kw in TECHNICAL_KEYWORDS)


def is_ops_mlops_rule_based(text: str) -> bool:
    """Returns True if post is about MLOps / LLMOps / AgentOps / DevOps."""
    if not isinstance(text, str) or not text.strip():
        return False

    text_lower = text.lower()
    ops_score = sum(1 for kw in OPS_KEYWORDS if kw in text_lower)

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

    ops_verbs = ['debug', 'deploy', 'monitor', 'fix', 'investigate', 'analyze', 'scale', 'configure', 'optimize']
    if len(text.split()) < 50 and any(v in text_lower for v in ops_verbs) and ops_score >= 1:
        return True

    if ops_score >= 3 or phrase_matches >= 2:
        return True

    if ops_score >= 2 or phrase_matches >= 1:
        operational_context = ['production', 'pipeline', 'infrastructure', 'latency', 'performance', 'availability', 'reliability', 'scale']
        if sum(1 for k in operational_context if k in text_lower) >= 1:
            return True

    return False
