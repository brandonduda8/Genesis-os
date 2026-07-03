from datetime import datetime
import time

from origami.memory.mission_store import MissionStore
from origami.providers.provider_manager import ProviderManager


class MissionExecutor:
    """
    Executes missions through the configured provider.
    """

    def __init__(self):
        self.providers = ProviderManager()
        self.store = MissionStore()

    def execute(self, mission):
        mission.started_at = datetime.utcnow().isoformat()
        start = time.perf_counter()

        try:
            provider = self.providers.get_provider(mission.capability)
            result = provider.execute(mission)

            mission.status = "completed"

        except Exception as exc:
            mission.status = "failed"
            mission.error = str(exc)

            result = {
                "success": False,
                "error": str(exc),
            }

        finally:
            mission.completed_at = datetime.utcnow().isoformat()
            mission.duration = round(
                time.perf_counter() - start,
                3,
            )

            self.store.save(mission)

        return result
