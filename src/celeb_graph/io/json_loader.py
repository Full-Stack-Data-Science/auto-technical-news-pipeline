from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from celeb_graph.models.relationship import RelationshipModel

def load_from_json(file_path: Union[str, Path]) -> RelationshipModel:
    """
    Deserialize a :class:`RelationshipModel` from a JSON file.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in file: {path}") from exc

    return RelationshipModel.from_dict(data)


def dump_to_json(
    model: RelationshipModel,
    file_path: Union[str, Path],
    *,
    indent: int = 2,
) -> None:
    """
    Serialize a :class:`RelationshipModel` to a JSON file.
    """
    path = Path(file_path)

    # Sets are not JSON-serializable – convert to sorted lists for stability.
    serializable = {
        user: {rel_type: sorted(targets) for rel_type, targets in rels.items()}
        for user, rels in model.to_dict().items()
    }

    with path.open("w", encoding="utf-8") as fh:
        json.dump(serializable, fh, indent=indent, ensure_ascii=False)