from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Job:
    id: str
    title: str
    description: str = ""
    priority: str = "normal"
    status: str = "queued"
    assigned_to: Optional[str] = None
    required_skills: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
