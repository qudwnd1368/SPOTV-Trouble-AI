from dataclasses import dataclass
from typing import Optional, Union


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


# Backward-compatible alias while older storage helpers are phased out.
Incident = KnowledgeItem
