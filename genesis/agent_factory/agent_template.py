class AgentTemplate:

    def __init__(
        self,
        name,
        role,
        skills,
        tools=None,
        status="idle",
        jobs_completed=0,
    ):
        self.name = name
        self.role = role
        self.skills = skills
        self.tools = tools or []
        self.status = status
        self.jobs_completed = jobs_completed

    def to_dict(self):
        return {
            "name": self.name,
            "role": self.role,
            "skills": self.skills,
            "tools": self.tools,
            "status": self.status,
            "jobs_completed": self.jobs_completed,
        }
