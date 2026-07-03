from pathlib import Path


class KnowledgeLoader:
    """
    Loads Genesis knowledge documents for Athena.
    """

    def __init__(self, root="genesis"):
        self.root = Path(root)

    def read(self):
        knowledge = {}

        if not self.root.exists():
            return knowledge

        for file in sorted(self.root.glob("*.md")):
            knowledge[file.stem] = file.read_text(encoding="utf-8")

        return knowledge
