class PermissionManager:
    """
    Controls which executives are allowed to use which capabilities.
    """

    def __init__(self):
        self._permissions = {}

    def allow(self, executive: str, capability: str):
        """
        Grant an executive permission to use a capability.
        """
        self._permissions.setdefault(executive, set()).add(capability)

    def deny(self, executive: str, capability: str):
        """
        Remove a capability from an executive.
        """
        if executive in self._permissions:
            self._permissions[executive].discard(capability)

    def can_execute(self, executive: str, capability: str) -> bool:
        """
        Check if an executive can execute a capability.
        """
        return capability in self._permissions.get(executive, set())

    def permissions(self, executive: str):
        """
        Return all capabilities assigned to an executive.
        """
        return sorted(self._permissions.get(executive, set()))

    def executives(self):
        """
        Return all registered executives.
        """
        return sorted(self._permissions.keys())

    def export(self):
        """
        Export permissions for persistence or debugging.
        """
        return {
            executive: sorted(capabilities)
            for executive, capabilities in self._permissions.items()
        }

    def load(self, data):
        """
        Restore permissions from a dictionary.
        """
        self._permissions = {
            executive: set(capabilities)
            for executive, capabilities in data.items()
        }
