# Genesis OS Architecture

## Core Components

OrigamiHarness
- Central orchestration layer.
- Coordinates workers, agents, tools, memory, and providers.

WorkerRegistry
- Discovers workers automatically.
- Selects the best worker based on capability and priority.

Workers
- Athena
- Builder
- ResearchBot
- DesignBot
- QABot

AgentRegistry
- Stores registered Genesis agents.
- Provides routing information.

MissionExecutor
- Executes routed missions through available providers.

ProviderManager
- Manages execution providers.
- Supports local and remote AI backends.

ToolRegistry
- Discovers and manages tools available to workers.

MemoryStore
- Stores project memory and mission history.

## Design Principles

- Plugin-first architecture.
- Small, focused workers.
- Modular components.
- Capability-based routing.
- Human approval for major architectural changes.
- Stable releases with versioned milestones.

## Current Release

v0.6.0

Highlights:
- Plugin worker architecture
- Automatic worker discovery
- Athena introduced
- Capability routing
