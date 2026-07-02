from origami.tools.echo import EchoTool


class ToolLoader:
    """
    Loads all available tools.
    """

    @staticmethod
    def load(registry):
        registry.register("echo", EchoTool())
