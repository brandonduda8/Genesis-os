import importlib
import inspect
import pkgutil

from .base import Worker


class WorkerRegistry:

    def __init__(self):
        self._workers = []

    def register(self, worker):
        self._workers.append(worker)

    def list(self):
        return [worker.name for worker in self._workers]

    def best(self, capability):
        matches = [
            w for w in self._workers
            if capability in w.capabilities
        ]

        if not matches:
            return None

        return sorted(
            matches,
            key=lambda w: w.priority,
            reverse=True,
        )[0]

    def discover(self, package_name="origami.workers"):
        package = importlib.import_module(package_name)

        for _, module_name, _ in pkgutil.iter_modules(package.__path__):

            if module_name in {
                "base",
                "registry",
                "__init__",
            }:
                continue

            module = importlib.import_module(
                f"{package_name}.{module_name}"
            )

            for _, obj in inspect.getmembers(module, inspect.isclass):

                if not issubclass(obj, Worker):
                    continue

                if obj is Worker:
                    continue

                # Skip abstract base classes like ExecutiveWorker
                if inspect.isabstract(obj):
                    continue

                self.register(obj())
