#!/usr/bin/env python3

import argparse

from origami.models.mission import Mission
from origami.scheduler.mission_scheduler import MissionScheduler
from origami.providers.provider_manager import ProviderManager
from origami.workers.registry import WorkerRegistry
from origami.knowledge.search import KnowledgeSearch
from origami.docs.generator import DocumentationGenerator
from origami.status.system_status import SystemStatus
from origami.memory.history import MissionHistory
from origami.memory.queue import MissionQueue
from origami.memory.stats import MissionStats
from origami.config.version import VERSION


def main():
    parser = argparse.ArgumentParser(description="Genesis OS CLI")
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Run a mission")
    run.add_argument("--capability", default="python")
    run.add_argument("--description", required=True)

    subparsers.add_parser("workers", help="List workers")
    subparsers.add_parser("providers", help="List providers")
    subparsers.add_parser("docs", help="Show documentation")
    subparsers.add_parser("status", help="Show system status")
    subparsers.add_parser("queue", help="Show mission queue")
    subparsers.add_parser("stats", help="Show mission statistics")
    subparsers.add_parser("version", help="Show version")

    knowledge = subparsers.add_parser(
        "knowledge",
        help="Search the knowledge base",
    )
    knowledge.add_argument("query")

    history = subparsers.add_parser(
        "history",
        help="Show mission history",
    )
    history.add_argument(
        "--status",
        choices=["queued", "completed", "failed"],
    )
    history.add_argument(
        "--capability",
    )

    show = subparsers.add_parser(
        "show",
        help="Show a mission by ID",
    )
    show.add_argument("mission_id")

    retry = subparsers.add_parser(
        "retry",
        help="Retry a mission by ID",
    )
    retry.add_argument("mission_id")

    args = parser.parse_args()

    if args.command == "run":
        scheduler = MissionScheduler()
        scheduler.submit(
            Mission(
                capability=args.capability,
                description=args.description,
                priority=10,
            )
        )
        print(scheduler.run_next())

    elif args.command == "workers":
        registry = WorkerRegistry()
        registry.discover()
        print(registry.list())

    elif args.command == "providers":
        print(ProviderManager().list())

    elif args.command == "knowledge":
        results = KnowledgeSearch().search(args.query)

        if not results:
            print("No matching knowledge found.")
        else:
            for section, content in results.items():
                print(f"\n=== {section.upper()} ===")
                print(content)

    elif args.command == "docs":
        summary = DocumentationGenerator().generate_summary()

        print(f"Genesis OS v{summary['version']}\n")

        print("Workers:")
        for worker in summary["workers"]:
            print(f"  - {worker}")

        print("\nProviders:")
        for provider in summary["providers"]:
            print(f"  - {provider}")

    elif args.command == "status":
        status = SystemStatus().summary()

        print(f"Genesis OS v{status['version']}\n")
        print("System Status")
        print("-------------")
        print(f"Workers: {len(status['workers'])}")
        print(f"Providers: {len(status['providers'])}")
        print(f"Pending Missions: {status['pending_missions']}")

    elif args.command == "history":
        history = MissionHistory()

        if args.status:
            missions = history.by_status(args.status)
        elif args.capability:
            missions = history.by_capability(args.capability)
        else:
            missions = history.all()

        print("Genesis OS Mission History")
        print("--------------------------")

        if not missions:
            print("No matching missions.")
        else:
            for mission in missions:
                print("-" * 40)
                print(f"ID: {mission['id']}")
                print(f"Capability: {mission['capability']}")
                print(f"Description: {mission['description']}")
                print(f"Priority: {mission['priority']}")
                print(f"Status: {mission['status']}")

    elif args.command == "show":
        history = MissionHistory()
        mission = history.get(args.mission_id)

        if mission is None:
            print("Mission not found.")
        else:
            print("Genesis OS Mission Details")
            print("--------------------------")
            print(f"ID:            {mission.get('id')}")
            print(f"Capability:    {mission.get('capability')}")
            print(f"Description:   {mission.get('description')}")
            print(f"Priority:      {mission.get('priority')}")
            print(f"Status:        {mission.get('status')}")
            print(f"Created At:    {mission.get('created_at')}")
            print(f"Started At:    {mission.get('started_at')}")
            print(f"Completed At:  {mission.get('completed_at')}")
            print(f"Duration:      {mission.get('duration')}")
            print(f"Error:         {mission.get('error')}")

    elif args.command == "retry":
        history = MissionHistory()
        mission = history.get(args.mission_id)

        if mission is None:
            print("Mission not found.")
        else:
            scheduler = MissionScheduler()
            scheduler.submit(
                Mission(
                    capability=mission["capability"],
                    description=mission["description"],
                    priority=mission["priority"],
                )
            )
            print(scheduler.run_next())

    elif args.command == "queue":
        queue = MissionQueue()

        print("Genesis OS Mission Queue")
        print("------------------------")

        if queue.empty():
            print("No pending missions.")
        else:
            for mission in queue.all():
                print(mission)

    elif args.command == "stats":
        stats = MissionStats().summary()

        print("Genesis OS Mission Statistics")
        print("-----------------------------")
        print(f"Total Missions:      {stats['total']}")
        print(f"Completed:           {stats['completed']}")
        print(f"Failed:              {stats['failed']}")
        print(f"Queued:              {stats['queued']}")
        print(f"Success Rate:        {stats['success_rate']}%")
        print(f"Average Duration:    {stats['average_duration']} sec")

    elif args.command == "version":
        print(f"Genesis OS v{VERSION}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
