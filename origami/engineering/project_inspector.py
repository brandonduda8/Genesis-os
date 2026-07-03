from pathlib import Path


class ProjectInspector:
    """
    Inspects the Genesis project and returns
    basic engineering statistics.
    """

    def __init__(self, root="."):
        self.root = Path(root)

    def summary(self):
        python_files = list(self.root.rglob("*.py"))
        markdown_files = list(self.root.rglob("*.md"))

        worker_files = [
            f for f in python_files
            if "origami/workers" in str(f).replace("\\", "/")
        ]

        executive_files = [
            f for f in worker_files
            if f.stem in ("ceo", "coo", "cto")
        ]

        todos = 0

        for file in python_files:
            try:
                text = file.read_text(encoding="utf-8")
            except Exception:
                continue

            todos += text.count("TODO")
            todos += text.count("FIXME")

        return {
            "python_files": len(python_files),
            "markdown_files": len(markdown_files),
            "workers": len(worker_files),
            "executives": len(executive_files),
            "todos": todos,
        }
