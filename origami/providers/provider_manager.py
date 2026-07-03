from origami.providers.local_provider import LocalProvider


class ProviderManager:
    """
    Registers and manages execution providers.
    """

    def __init__(self):
        self.providers = {}
        self.register(LocalProvider())

    def register(self, provider):
        self.providers[provider.name] = provider

    def get(self, name="LocalProvider"):
        return self.providers.get(name)

    def get_provider(self, capability=None):
        """
        Returns the appropriate provider for a mission.

        Future versions can route based on capability or
        provider configuration. For now, always return the
        default LocalProvider.
        """
        return self.get()

    def list(self):
        return list(self.providers.keys())
