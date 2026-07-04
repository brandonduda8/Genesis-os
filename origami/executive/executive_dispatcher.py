class ExecutiveDispatcher:

    def __init__(self, registry):
        self.registry = registry

    def dispatch(self, mission):

        candidates = self.registry.by_skill(
            mission["capability"]
        )

        if not candidates:
            return None

        return candidates[0]
