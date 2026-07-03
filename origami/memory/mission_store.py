import json
from pathlib import Path

from origami.models.mission import Mission


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

    def save(self, mission: Mission):
        missions = self._load()

        record = mission.to_dict()

        for index, existing in enumerate(missions):
            if existing["id"] == mission.id:
                missions[index] = record
                break
        else:
            missions.append(record)

        self._save(missions)

    def save_all(self, missions):
        self._save(missions)

    def all(self):
        return self._load()

    def clear(self):
        self._save([])
