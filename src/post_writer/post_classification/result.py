from dataclasses import dataclass, field
from typing import List


@dataclass
class ClassificationResult:
    labels: List[str]
    is_technical: bool
    exit_stage: str  # "pre_filter" | "rule_based" | "zero_shot_binary" | "zero_shot_multi"
    scores: dict = field(default_factory=dict)
