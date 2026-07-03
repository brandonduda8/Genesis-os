from origami.models.mission import Mission
from origami.scheduler.mission_scheduler import MissionScheduler
from origami.engineering.mission_generator import EngineeringMissionGenerator


class EngineeringApproval:

    def approve(self, index):
        missions = EngineeringMissionGenerator().generate()

        if index < 0 or index >= len(missions):
            raise IndexError("Invalid mission index.")

        recommendation = missions[index]

        priority_map = {
            "high": 100,
            "medium": 50,
            "low": 10,
        }

        mission = Mission(
            capability="engineering",
            description=recommendation["title"],
            priority=priority_map.get(
                recommendation["priority"],
                10,
            ),
        )

        scheduler = MissionScheduler()
        scheduler.submit(mission)

        return {
            "approved": True,
            "mission": recommendation,
            "mission_id": mission.id,
        }
