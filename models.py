from dataclasses import dataclass, field
from typing import Any, Optional, Union


@dataclass
class KnowledgeItem:
    id: Optional[Union[int, str]]
    title: str
    context: str
    action: str
    caution: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    embedding: Optional[str] = None
    images: list[dict[str, Any]] = field(default_factory=list)


# Backward-compatible alias while older storage helpers are phased out.
Incident = KnowledgeItem
