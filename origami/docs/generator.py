from origami.config.version import VERSION
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
            "version": VERSION,
            "workers": registry.list(),
            "providers": providers.list(),
        }
