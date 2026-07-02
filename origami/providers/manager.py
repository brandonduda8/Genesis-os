class ProviderManager:
    """
    Registers and manages execution providers.
    """

    def __init__(self):
        self.providers = {}

    def register(self, name, provider):
        self.providers[name.lower()] = provider

    def get(self, name):
        return self.providers.get(name.lower())

    def list(self):
        return list(self.providers.keys())

    def health(self):
        return {
            name: provider.health()
            for name, provider in self.providers.items()
        }

    def choose(self, capability=None):
        """
        For now, always choose Genesis.
        Later this will become an intelligent selector.
        """
        return self.providers.get("genesis")
