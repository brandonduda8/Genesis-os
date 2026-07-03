#!/usr/bin/env python3

import argparse

from origami.models.mission import Mission
from origami.scheduler.mission_scheduler import MissionScheduler
from origami.providers.provider_manager import ProviderManager
from origami.workers.registry import WorkerRegistry

VERSION = "0.9.1"


def main():
    parser = argparse.ArgumentParser(description="Genesis OS CLI")

    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Run a mission")
    run.add_argument("--capability", default="python")
    run.add_argument("--description", required=True)

    subparsers.add_parser("workers", help="List available workers")
    subparsers.add_parser("providers", help="List available providers")
    subparsers.add_parser("version", help="Show Genesis OS version")

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

    elif args.command == "version":
        print(f"Genesis OS v{VERSION}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
