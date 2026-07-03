from origami.providers.local_provider import LocalProvider


class MissionExecutor:
    """
    Executes missions through a configured provider.
    """

    def __init__(self, provider=None):
        self.provider = provider or LocalProvider()

    def execute(self, mission):
        return self.provider.execute(mission)
