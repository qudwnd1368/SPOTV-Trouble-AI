from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class Incident:
    id: Optional[Union[int, str]]
    incident_number: str
    occurred_at: Optional[str]
    equipment: str
    symptom: str
    cause: str
    action: str
    notes: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    embedding: Optional[str] = None
