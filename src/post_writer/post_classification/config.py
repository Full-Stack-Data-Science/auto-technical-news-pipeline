from dataclasses import dataclass


@dataclass
class ClassificationConfig:
    tech_threshold: float = 0.52
    score_margin: float = 0.06
    min_words: int = 25
    model_name: str = "facebook/bart-large-mnli"
