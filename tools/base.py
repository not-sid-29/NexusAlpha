"""Nexus Tools — Abstract base class for all tools."""

from abc import ABC, abstractmethod


class BaseTool(ABC):
    """Abstract base class that all Nexus tools must extend.

    Every tool must implement:
        - execute(params): Run the tool operation
        - get_manifest(): Return MCP manifest for this tool
        - validate_input(params): Validate input against tool schema
    """

    @abstractmethod
    async def execute(self, params) -> dict:
        """Execute the tool operation and return result dict."""
        ...

    @abstractmethod
    def get_manifest(self) -> dict:
        """Return MCP tool manifest (name, description, input_schema)."""
        ...

    @abstractmethod
    def validate_input(self, params) -> bool:
        """Validate input parameters against tool schema."""
        ...

    @property
    @abstractmethod
    def tool_id(self) -> str:
        """Return the tool's identifier (e.g. 'FILE_SYSTEM', 'GIT_OPS')."""
        ...
