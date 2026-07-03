#!/usr/bin/env python3

import argparse

from origami.config.version import VERSION
from origami.models.mission import Mission
from origami.scheduler.mission_scheduler import MissionScheduler
from origami.providers.provider_manager import ProviderManager
from origami.workers.registry import WorkerRegistry
from origami.knowledge.search import KnowledgeSearch
from origami.docs.generator import DocumentationGenerator
from origami.status.system_status import SystemStatus
from origami.memory.history import MissionHistory
from origami.memory.queue import MissionQueue


def main():
    parser = argparse.ArgumentParser(description="Genesis OS CLI")

    subparsers = parser.add_subparsers(dest="command")

    # Run mission
    run = subparsers.add_parser("run", help="Run a mission")
    run.add_argument("--capability", default="python")
    run.add_argument("--description", required=True)

    # Workers
    subparsers.add_parser("workers", help="List available workers")

    # Providers
    subparsers.add_parser("providers", help="List available providers")

    # Knowledge
    knowledge = subparsers.add_parser(
        "knowledge",
        help="Search the Genesis knowledge base",
    )
    knowledge.add_argument("query")

    # Documentation
    subparsers.add_parser(
        "docs",
        help="Show generated system documentation",
    )

    # System status
    subparsers.add_parser(
        "status",
        help="Show Genesis OS system status",
    )

    # Mission history
    subparsers.add_parser(
        "history",
        help="Show mission history",
    )

    # Mission queue
    subparsers.add_parser(
        "queue",
        help="Show queued missions",
    )

    # Version
    subparsers.add_parser(
        "version",
        help="Show Genesis OS version",
    )

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
        manager = ProviderManager()
        print(manager.list())

    elif args.command == "knowledge":
        search = KnowledgeSearch()
        results = search.search(args.query)

        if not results:
            print("No matching knowledge found.")
        else:
            for section, content in results.items():
                print(f"\n=== {section.upper()} ===")
                print(content)

    elif args.command == "docs":
        docs = DocumentationGenerator()
        summary = docs.generate_summary()

        print(f"Genesis OS v{summary['version']}\n")

        print("Workers:")
        for worker in summary["workers"]:
            print(f"  - {worker}")

        print("\nProviders:")
        for provider in summary["providers"]:
            print(f"  - {provider}")

    elif args.command == "status":
        status = SystemStatus()
        summary = status.summary()

        print(f"Genesis OS v{summary['version']}\n")

        print("System Status")
        print("-------------")
        print(f"Workers: {len(summary['workers'])}")
        print(f"Providers: {len(summary['providers'])}")
        print(f"Pending Missions: {summary['pending_missions']}")

        print("\nAvailable Workers")
        print("-----------------")
        for worker in summary["workers"]:
            print(f"- {worker}")

        print("\nAvailable Providers")
        print("-------------------")
        for provider in summary["providers"]:
            print(f"- {provider}")

    elif args.command == "history":
        history = MissionHistory()
        missions = history.all()

        print("Genesis OS Mission History")
        print("--------------------------")

        if not missions:
            print("No missions found.")
        else:
            for mission in missions:
                print(f"\nID: {mission['id']}")
                print(f"Capability: {mission['capability']}")
                print(f"Description: {mission['description']}")
                print(f"Priority: {mission['priority']}")
                print(f"Status: {mission['status']}")

    elif args.command == "queue":
        queue = MissionQueue()
        missions = queue.all()

        print("Genesis OS Mission Queue")
        print("------------------------")

        if not missions:
            print("No pending missions.")
        else:
            for mission in missions:
                print(f"\nID: {mission['id']}")
                print(f"Capability: {mission['capability']}")
                print(f"Description: {mission['description']}")
                print(f"Priority: {mission['priority']}")
                print(f"Status: {mission['status']}")

    elif args.command == "version":
        print(f"Genesis OS v{VERSION}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
