from genesis.agents.base_agent import BaseAgent
from genesis.knowledge.knowledge_base import KnowledgeBase


class ResearchAgent(BaseAgent):

    name = "Research"

    def __init__(self):
        self.kb = KnowledgeBase()

    def research(self, topic):

        print(f"🔍 Researching: {topic}")

        # Placeholder until web search is integrated.
        summary = f"Research summary for '{topic}'."

        self.kb.save(
            "research",
            topic,
            summary
        )

        return summary
