from origami.security.permission_manager import PermissionManager


class ToolManager:
    """
    Central registry for all executable tools.

    Responsibilities:
    - Register tools
    - Discover tools by capability
    - Enforce permissions
    - Execute tasks
    """

    def __init__(self):
        self._tools = {}
        self.permissions = PermissionManager()

    def register(self, tool):
        """Register a Tool implementation."""
        self._tools[tool.name] = tool

    def unregister(self, name):
        """Remove a tool from the registry."""
        self._tools.pop(name, None)

    def get(self, name):
        """Return a tool by name."""
        return self._tools.get(name)

    def tools(self):
        """List registered tool names."""
        return sorted(self._tools.keys())

    def capabilities(self):
        """Return every capability available across all tools."""
        capabilities = set()

        for tool in self._tools.values():
            capabilities.update(tool.capabilities())

        return sorted(capabilities)

    def find(self, capability):
        """Find the first tool supporting a capability."""
        for tool in self._tools.values():
            if capability in tool.capabilities():
                return tool
        return None

    def execute(self, executive, capability, task):
        """
        Execute a task using the appropriate tool.
        """

        if not self.permissions.can_execute(executive, capability):
            raise PermissionError(
                f"{executive} is not permitted to execute '{capability}'."
            )

        tool = self.find(capability)

        if tool is None:
            raise ValueError(
                f"No registered tool supports '{capability}'."
            )

        return tool.execute(task)

    def status(self):
        """Return diagnostic information."""
        return {
            "tool_count": len(self._tools),
            "tools": self.tools(),
            "capabilities": self.capabilities(),
            "executives": self.permissions.executives(),
        }
