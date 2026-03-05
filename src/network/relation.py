from enum import Enum
from typing import Dict, Set, Union
from pathlib import Path
import json

class RelationType(Enum):
    FOLLOW  = "follow"   
    MENTION = "mention"

class RelationshipModel:
    """
    Stores relationships in a normalized structure.

    Internal structure:
    {
        "userA": {
            "follow":   set([...]),
            "mention": set([...])
        },
        ...
    }
    """

    def __init__(self):
        self._relations = {}

    def add(
        self,
        relation: RelationType,
        source_user: str,
        target_user: str,
    ) -> None:
        self._init_user_relations(source_user)
        self._init_user_relations(target_user)
        self._relations[source_user][relation.value].add(target_user)
    
    def from_dict(self, data):
        self._relations = {}
        for user, relations in data.items():
            self._init_user_relations(user)
            for relation_type, targets in relations.items():
                
                if relation_type not in {rt.value for rt in RelationType}:
                    raise ValueError(f"Unknown relation type: {relation_type}")

                for target in targets:
                    self._init_user_relations(target)
                    self._relations[user][relation_type].add(target)

    def to_dict(self) -> Dict[str, Dict[str, Set[str]]]:
        return self._relations
    
    def _init_user_relations(self, user):
        if user not in self._relations:
            self._relations[user] = {
                type.value: set() for type in RelationType
            }


def load_relationship_model_from_json(
    file_path: Union[str, Path]
) -> RelationshipModel:
    """
    Load RelationshipModel from a JSON file.

    Expected JSON structure:
    {
        "userA": {
            "follow": ["userB", "userC"],
            "mention": ["userD"]
        }
    }
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {path}") from exc

    model = RelationshipModel()
    model.from_dict(data)

    return model
