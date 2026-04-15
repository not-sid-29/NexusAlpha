"""Nexus Agents — Abstract base class for all agents."""

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Abstract base class that all Nexus sub-agents must extend.

    Every agent must implement:
        - handle_task(message): Process a TOON TASK message
        - validate_result(output): Validate its own output before publishing
        - get_scope(): Return the context scope this agent operates in
    """

    @abstractmethod
    async def handle_task(self, message) -> None:
        """Process a TOON TASK message and publish RESULT or ERROR."""
        ...

    @abstractmethod
    def validate_result(self, output) -> bool:
        """Validate agent output before it leaves the agent boundary."""
        ...

    @abstractmethod
    def get_scope(self) -> str:
        """Return the context scope identifier for this agent."""
        ...

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Return the agent's identifier (e.g. 'PLANNER', 'CODER')."""
        ...
