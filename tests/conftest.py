import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Create a fixture for the event loop
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Create a fixture for mocking aiohttp ClientSession
@pytest.fixture
async def mock_session():
    """Mock aiohttp ClientSession for tests."""
    session = AsyncMock()
    async def mock_close():
        pass
    session.close = mock_close
    return session

# Create a fixture for the AsyncContextManagerMock
class AsyncContextManagerMock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.fixture
def async_context_manager():
    """Fixture for async context manager mock."""
    return AsyncContextManagerMock()
