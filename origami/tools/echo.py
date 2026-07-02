from origami.tools.base import Tool


class EchoTool(Tool):
    name = "echo"
    description = "Returns the supplied text."

    def run(self, text):
        return text
