class Coordinator:

    def __init__(self, agent_repository):
        self.agent_repository = agent_repository

    def assign(self, job):
        agents = self.agent_repository.list()

        if not agents:
            print("⚠ No agents available.")
            return None

        title = job.title.lower()

        for agent in agents:
            name, role, skills, status, completed = agent

            role = role.lower()

            if title == "research" and "research" in role:
                print(f"🤖 Assigned '{job.title}' to {name}")
                return type("Agent", (), {"name": name})()

            if title == "design" and (
                "architecture" in role or "design" in role
            ):
                print(f"🤖 Assigned '{job.title}' to {name}")
                return type("Agent", (), {"name": name})()

            if title == "implementation" and (
                "development" in role or "developer" in role
            ):
                print(f"🤖 Assigned '{job.title}' to {name}")
                return type("Agent", (), {"name": name})()

            if title == "testing" and "testing" in role:
                print(f"🤖 Assigned '{job.title}' to {name}")
                return type("Agent", (), {"name": name})()

        name = agents[0][0]
        print(f"🤖 Assigned '{job.title}' to {name} (fallback)")
        return type("Agent", (), {"name": name})()
