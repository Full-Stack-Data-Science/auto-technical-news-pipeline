from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set
from enum import Enum
 
class RelationType(Enum):
    FOLLOW  = "follow"
    MENTION = "mention"
 
@dataclass(frozen=True)
class Relation:
    source: str
    relation_type: RelationType
    target: str

# Alias for the internal nested dict type
_RelationsDict = Dict[str, Dict[str, Set[str]]]

class RelationshipModel:
    """
    Stores directed relationships between users.

    Internal layout
    ---------------
    {
        "userA": {
            "follow":  {"userB", "userC"},
            "mention":  {"userD"},
        },
        ...
    }
    """

    def __init__(self) -> None:
        self._relations: _RelationsDict = {}

    @classmethod
    def from_dict(cls, data: dict) -> "RelationshipModel":
        """
        Build a RelationshipModel from a plain dict.

        Expected shape
        --------------
        {
            "userA": {
                "follow":  ["userB", "userC"],
                "mention": ["userD"]
            }
        }
        """
        valid_types = {rt.value for rt in RelationType}
        model = cls()

        for user, relations in data.items():
            model._init_user(user)

            for relation_type, targets in relations.items():
                if relation_type not in valid_types:
                    raise ValueError(
                        f"Unknown relation type {relation_type!r}. "
                        f"Expected one of: {sorted(valid_types)}"
                    )
                for target in targets:
                    model._init_user(target)
                    model._relations[user][RelationType(relation_type)].add(target)
        return model

    def add(
        self,
        relation: Relation
    ) -> None:
        """Record a single directed relationship."""
        self._init_user(relation.source)
        self._init_user(relation.target)
        self._relations[relation.source][relation.relation_type].add(relation.target)

    def _init_user(self, user: str) -> None:
        if user not in self._relations:
            self._relations[user] = {type: set() for type in RelationType}

    def to_dict(self) -> dict:
        """
        Serialize to a plain dict with sorted lists as targets.
 
        Produces stable, diff-friendly output suitable for JSON serialization.
        """
        return {
            source: {
                rel_type.value: sorted(targets)
                for rel_type, targets in relation_map.items()
            }
            for source, relation_map in self._relations.items()
        }
    

model = RelationshipModel.from_dict({
            "alice": {"follow": ["bob", "carol"], "mention": ["dave"]},
            "bob":   {"follow": ["carol"],        "mention": []},
            "carol": {"follow": [],               "mention": ["alice"]},
        })
