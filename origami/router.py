class CapabilityRouter:

    def __init__(self, registry):
        self.registry = registry

    def find(self, capability):
        capability = capability.lower()

        matches = []

        for agent in self.registry.all().values():
            caps = [c.lower() for c in agent["capabilities"]]

            if capability in caps:
                matches.append(agent)

        matches.sort(
            key=lambda a: (
                a["active_jobs"],
                a["name"],
            )
        )

        return matches

    def best(self, capability):
        matches = self.find(capability)

        if matches:
            return matches[0]

        return None
