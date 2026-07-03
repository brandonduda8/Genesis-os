import json
from pathlib import Path


class MissionStore:
    """
    Persists Genesis OS missions to disk.
    """

    def __init__(self, path="origami/memory/missions.json"):
        self.path = Path(path)

        if not self.path.exists():
            self.path.write_text("[]")

    def _load(self):
        return json.loads(self.path.read_text())

    def _save(self, missions):
        self.path.write_text(json.dumps(missions, indent=4))

    def save(self, mission):
        missions = self._load()

        record = {
            "id": mission.id,
            "capability": mission.capability,
            "description": mission.description,
            "priority": mission.priority,
            "status": mission.status,
        }

        for index, existing in enumerate(missions):
            if existing["id"] == mission.id:
                missions[index] = record
                break
        else:
            missions.append(record)

        self._save(missions)

    def all(self):
        return self._load()

    def clear(self):
        self._save([])
