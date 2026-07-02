class AgentCoordinator:

    def __init__(self, agent_repository):
        self.agent_repository = agent_repository

    def assign(self, job):
        agents = self.agent_repository.list()

        if not agents:
            print("⚠️ No agents available.")
            return None

        title = job.title.lower()

        for agent in agents:
            name, role, skills, status, jobs_completed = agent

            skill_list = [s.strip().lower() for s in skills.split(",")]

            if "research" in title and "research" in skill_list:
                print(f"🤖 Assigned '{job.title}' to {name}")
                return agent

            if "design" in title and "design" in skill_list:
                print(f"🤖 Assigned '{job.title}' to {name}")
                return agent

            if "implementation" in title and (
                "python" in skill_list or
                "development" in skill_list or
                "coding" in skill_list
            ):
                print(f"🤖 Assigned '{job.title}' to {name}")
                return agent

            if "testing" in title and (
                "testing" in skill_list or
                "qa" in skill_list
            ):
                print(f"🤖 Assigned '{job.title}' to {name}")
                return agent

        # Fallback to first available agent
        agent = agents[0]
        print(f"🤖 Assigned '{job.title}' to {agent[0]} (fallback)")
        return agent
