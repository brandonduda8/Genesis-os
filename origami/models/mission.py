from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Mission:
    capability: str
    description: str
    priority: int = 0
    status: str = "queued"
    created_at: datetime = field(default_factory=datetime.utcnow)
