import json

class MemoryEngine:

    def save(self, mission, results):
        data = {
            "mission": mission,
            "results": results
        }

        with open("genesis/memory.json", "w") as f:
            json.dump(data, f, indent=4)

        print("🧠 Memory Updated")
