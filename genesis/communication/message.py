from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any

@dataclass
class Message:
    sender: str
    recipient: str
    subject: str
    content: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
