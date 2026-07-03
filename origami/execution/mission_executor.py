from origami.config.providers import DEFAULT_PROVIDER
from origami.providers.provider_manager import ProviderManager


class MissionExecutor:
    """
    Executes missions through the configured ProviderManager.
    """

    def __init__(self):
        self.providers = ProviderManager()

    def execute(self, mission):
        provider = self.providers.get(DEFAULT_PROVIDER)

        if provider is None:
            mission.status = "failed"
            return {
                "success": False,
                "error": f"Provider '{DEFAULT_PROVIDER}' not found",
            }

        return provider.execute(mission)
