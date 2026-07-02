class SystemStatus:
    """
    Reports the overall health of the Origami system.
    """

    def __init__(self, harness):
        self.harness = harness

    def report(self):
        return {
            "agents": self.harness.registry.count(),
            "providers": self.harness.executor.providers.list(),
            "provider_health": self.harness.executor.providers.health(),
            "registered_agents": list(
                self.harness.registry.all().keys()
            ),
        }
