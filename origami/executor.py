from origami.providers.manager import ProviderManager
from origami.providers.loader import ProviderLoader


class MissionExecutor:

    def __init__(self, kernel, harness):
        self.kernel = kernel
        self.harness = harness

        self.providers = ProviderManager()
        ProviderLoader.load(kernel, self.providers)

    def execute(self, mission, provider=None):

        route = self.harness.route(mission)
        capability = route["capability"]

        if capability is None:
            return {
                "success": False,
                "reason": "No capability identified.",
                "route": route,
            }

        #
        # Native worker execution
        #
        worker = self.harness.workers.best(capability)

        if worker is not None:
            result = worker.execute(mission)
            result["execution"] = "worker"
            result["capability"] = capability
            return result

        #
        # Existing database-agent execution
        #
        if route["agent"] is None:
            return {
                "success": False,
                "reason": "No capable agent found.",
                "route": route,
            }

        engine = (
            self.providers.get(provider)
            if provider
            else self.providers.choose(capability)
        )

        if engine is None:
            return {
                "success": False,
                "reason": "No execution provider available.",
            }

        result = engine.execute(mission)
        result["agent"] = route["agent"]["name"]
        result["capability"] = capability
        result["execution"] = "provider"

        return result
