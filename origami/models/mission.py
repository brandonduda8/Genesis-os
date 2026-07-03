from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class Mission:
    capability: str
    description: str
    priority: int = 0

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "queued"

    created_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self):
        return {
            "id": self.id,
            "capability": self.capability,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data):
        mission = cls(
            capability=data["capability"],
            description=data["description"],
            priority=data.get("priority", 0),
        )

        mission.id = data.get("id", mission.id)
        mission.status = data.get("status", "queued")
        mission.created_at = data.get("created_at", mission.created_at)
        mission.started_at = data.get("started_at")
        mission.completed_at = data.get("completed_at")
        mission.duration = data.get("duration")
        mission.error = data.get("error")

        return mission
