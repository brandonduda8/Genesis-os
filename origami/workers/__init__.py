"""
Origami Worker Framework

This package provides a unified interface for all native
and external workers.
"""

from .base import Worker
from .registry import WorkerRegistry
from .manager import WorkerManager

__all__ = [
    "Worker",
    "WorkerRegistry",
    "WorkerManager",
]
