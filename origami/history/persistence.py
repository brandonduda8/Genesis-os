import json
import os


class Persistence:
    """
    Save and restore Genesis state.
    """

    def __init__(self, filename="genesis_state.json"):
        self.filename = filename

    def save(self, state):
        with open(self.filename, "w") as f:
            json.dump(state, f, indent=4)

    def load(self):
        if not os.path.exists(self.filename):
            return {
                "history": [],
                "executives": {},
            }

        with open(self.filename, "r") as f:
            return json.load(f)
