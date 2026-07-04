from origami.tools.tool import Tool


class OnepageTool(Tool):
    """
    Adapter for a Onepage service.

    Replace the placeholder implementation with the official
    Onepage API/CLI when available.
    """

    @property
    def name(self):
        return "Onepage"

    def capabilities(self):
        return [
            "generate_site",
            "edit_site",
            "publish_site",
            "analyze_site",
        ]

    def execute(self, task):
        action = task.get("action", "")

        return {
            "tool": self.name,
            "action": action,
            "status": "placeholder",
            "message": (
                "Onepage adapter installed. "
                "Connect the official API or CLI here."
            ),
            "task": task,
        }
