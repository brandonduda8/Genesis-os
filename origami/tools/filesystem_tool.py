from pathlib import Path

from origami.tools.tool import Tool


class FilesystemTool(Tool):

    @property
    def name(self):
        return "Filesystem"

    def capabilities(self):
        return [
            "read_file",
            "write_file",
            "list_directory",
        ]

    def execute(self, task):
        action = task["action"]

        if action == "read_file":
            return {
                "content": Path(task["path"]).read_text()
            }

        if action == "write_file":
            Path(task["path"]).write_text(task["content"])
            return {"status": "ok"}

        if action == "list_directory":
            return {
                "files": [
                    str(p) for p in Path(task["path"]).iterdir()
                ]
            }

        raise ValueError(action)
