"""NexusAlpha — Shared test fixtures."""

import pytest
import pytest_asyncio


@pytest.fixture
def event_loop():
    """Provide an event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_bus():
    """Mock TOON message bus for testing."""
    # TODO: Implement mock bus
    pass


@pytest_asyncio.fixture
async def mock_model():
    """Mock model provider for testing."""
    # TODO: Implement mock model
    pass
