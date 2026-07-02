import json
from pathlib import Path


class KnowledgeBase:

    def __init__(self):
        self.db = Path("genesis/knowledge/knowledge.json")

        if not self.db.exists():
            self.db.parent.mkdir(parents=True, exist_ok=True)
            self.db.write_text("{}")

    def load(self):
        return json.loads(self.db.read_text())

    def save(self, category, title, content):

        data = self.load()

        if category not in data:
            data[category] = []

        data[category].append({
            "title": title,
            "content": content
        })

        self.db.write_text(json.dumps(data, indent=4))

        print(f"📚 Saved knowledge: {title}")
