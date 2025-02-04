from datetime import datetime

import pytest

from ..agents.base_agent import BaseAgent


class TestAgent(BaseAgent):
    """Test implementation of BaseAgent"""

    async def start(self):
        self.status = "active"
        self.last_update = datetime.now().isoformat()

    async def stop(self):
        self.status = "inactive"
        self.last_update = datetime.now().isoformat()

    async def update_config(self, new_config):
        self.config = new_config
        self.last_update = datetime.now().isoformat()


@pytest.fixture
def test_agent():
    return TestAgent("test_id", "Test Agent", {"test": "config"})


@pytest.mark.asyncio
async def test_agent_initialization(test_agent):
    assert test_agent.agent_id == "test_id"
    assert test_agent.name == "Test Agent"
    assert test_agent.config == {"test": "config"}
    assert test_agent.status == "inactive"
    assert test_agent.last_update is None


@pytest.mark.asyncio
async def test_agent_start(test_agent):
    assert test_agent.status == "inactive"
    await test_agent.start()
    assert test_agent.status == "active"
    assert test_agent.last_update is not None


@pytest.mark.asyncio
async def test_agent_stop(test_agent):
    await test_agent.start()
    assert test_agent.status == "active"
    await test_agent.stop()
    assert test_agent.status == "inactive"


@pytest.mark.asyncio
async def test_agent_update_config(test_agent):
    new_config = {"updated": "config"}
    await test_agent.update_config(new_config)
    assert test_agent.config == new_config
    assert test_agent.last_update is not None


@pytest.mark.asyncio
async def test_get_status(test_agent):
    status = test_agent.get_status()
    assert status["id"] == test_agent.agent_id
    assert status["name"] == test_agent.name
    assert status["status"] == test_agent.status
    assert status["config"] == test_agent.config
