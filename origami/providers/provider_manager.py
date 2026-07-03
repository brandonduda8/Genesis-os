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

    def list(self):
        return list(self.providers.keys())
