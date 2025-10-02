from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass(slots=True)
class Clause:
    """Structured representation of a lease contract clause."""

    id: str
    level: int
    index_path: List[str] = field(default_factory=list)
    start: int = 0
    end: int = 0
    text: str = ""
    tags: List[str] = field(default_factory=list)
    title: Optional[str] = None

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict, omitting empty optionals."""

        data = asdict(self)
        if self.title is None:
            data.pop("title", None)
        return data


__all__ = ["Clause"]


