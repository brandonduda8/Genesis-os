class Provider:
    """
    Base interface for all execution providers.
    """

    @property
    def name(self):
        return self.__class__.__name__

    def execute(self, mission):
        raise NotImplementedError("Providers must implement execute().")
