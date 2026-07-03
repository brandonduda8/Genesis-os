from origami.providers.provider_manager import ProviderManager
from origami.workers.registry import WorkerRegistry


class DocumentationGenerator:
    """
    Generates project documentation from the current system state.
    """

    def generate_summary(self):
        registry = WorkerRegistry()
        registry.discover()

        providers = ProviderManager()

        return {
            "version": "1.0.0-beta1",
            "workers": registry.list(),
            "providers": providers.list(),
        }
