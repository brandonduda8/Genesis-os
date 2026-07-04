from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class MissionAssignment:
    executive: str
    role: str
    mission: Dict[str, Any]


class ExecutiveDispatcher:
    """
    Assign missions to executives based on skills.
    """

    def __init__(self, registry):
        self.registry = registry

    def dispatch(self, missions: List[Dict[str, Any]]) -> List[MissionAssignment]:
        assignments = []

        for mission in missions:
            capability = mission.get("capability", "")

            candidates = self.registry.by_skill(capability)

            if not candidates:
                candidates = self.registry.by_skill("architecture")

            if not candidates:
                continue

            executive = candidates[0]

            assignments.append(
                MissionAssignment(
                    executive=executive["name"],
                    role=executive["role"],
                    mission=mission,
                )
            )

        return assignments
