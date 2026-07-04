class CapabilityRegistry:

    def __init__(self):
        self.capabilities = {}

    def register(self, capability, tool):

        self.capabilities.setdefault(capability, [])
        self.capabilities[capability].append(tool)

    def find(self, capability):
        return self.capabilities.get(capability, [])

    def all(self):
        return self.capabilities
