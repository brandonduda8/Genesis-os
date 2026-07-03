from origami.providers.provider_manager import ProviderManager


class MissionExecutor:
    """
    Executes missions through the configured ProviderManager.
    """

    def __init__(self):
        self.providers = ProviderManager()

    def execute(self, mission, provider="LocalProvider"):
        execution_provider = self.providers.get(provider)

        if execution_provider is None:
            mission.status = "failed"
            return {
                "success": False,
                "error": f"Provider '{provider}' not found",
            }

        return execution_provider.execute(mission)
