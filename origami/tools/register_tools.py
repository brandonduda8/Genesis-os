from origami.tools.tool_manager import ToolManager

from origami.tools.filesystem_tool import FilesystemTool
from origami.tools.onepage_tool import OnepageTool


def build_tool_manager():

    tm = ToolManager()

    tm.register(FilesystemTool())
    tm.register(OnepageTool())

    return tm
