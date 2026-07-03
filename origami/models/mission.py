from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class Mission:
    """
    Represents a Genesis OS mission.
    """

    capability: str
    description: str
    priority: int
    status: str = "queued"
    id: str = field(default_factory=lambda: str(uuid4()))
