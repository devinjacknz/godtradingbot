import pytest

from ..agents.trading_agent import TradingAgent
from ..services.agent_manager import AgentManager


@pytest.fixture
def agent_config():
    return {
        "strategy_type": "momentum",
        "parameters": {"riskLevel": "medium", "tradeSize": 5},
    }


@pytest.fixture
async def agent_manager():
    manager = AgentManager()
    yield manager
    # 清理: 停止所有代理
    await manager.stop_all_agents()


@pytest.mark.asyncio
async def test_create_agent(agent_manager, agent_config):
    agent = await agent_manager.create_agent("test_1", "Test Agent", agent_config)

    assert isinstance(agent, TradingAgent)
    assert agent.agent_id == "test_1"
    assert agent.name == "Test Agent"
    assert agent.config == agent_config


@pytest.mark.asyncio
async def test_create_duplicate_agent(agent_manager, agent_config):
    await agent_manager.create_agent("test_1", "Test Agent", agent_config)

    with pytest.raises(ValueError):
        await agent_manager.create_agent("test_1", "Duplicate Agent", agent_config)


@pytest.mark.asyncio
async def test_get_agent(agent_manager, agent_config):
    await agent_manager.create_agent("test_1", "Test Agent", agent_config)

    agent = await agent_manager.get_agent("test_1")
    assert agent is not None
    assert agent.agent_id == "test_1"

    non_existent = await agent_manager.get_agent("non_existent")
    assert non_existent is None


@pytest.mark.asyncio
async def test_update_agent(agent_manager, agent_config):
    await agent_manager.create_agent("test_1", "Test Agent", agent_config)

    new_config = {
        "strategy_type": "scalping",
        "parameters": {"riskLevel": "high", "tradeSize": 10},
    }

    updated_agent = await agent_manager.update_agent("test_1", new_config)
    assert updated_agent is not None
    assert updated_agent.config == new_config

    # 测试更新不存在的代理
    non_existent = await agent_manager.update_agent("non_existent", new_config)
    assert non_existent is None


@pytest.mark.asyncio
async def test_delete_agent(agent_manager, agent_config):
    await agent_manager.create_agent("test_1", "Test Agent", agent_config)

    # 删除存在的代理
    success = await agent_manager.delete_agent("test_1")
    assert success is True

    # 确认代理已被删除
    agent = await agent_manager.get_agent("test_1")
    assert agent is None

    # 尝试删除不存在的代理
    success = await agent_manager.delete_agent("non_existent")
    assert success is False


@pytest.mark.asyncio
async def test_start_stop_agent(agent_manager, agent_config):
    await agent_manager.create_agent("test_1", "Test Agent", agent_config)

    # 启动代理
    success = await agent_manager.start_agent("test_1")
    assert success is True

    agent = await agent_manager.get_agent("test_1")
    assert agent.status == "active"

    # 停止代理
    success = await agent_manager.stop_agent("test_1")
    assert success is True

    agent = await agent_manager.get_agent("test_1")
    assert agent.status == "inactive"

    # 测试不存在的代理
    success = await agent_manager.start_agent("non_existent")
    assert success is False


@pytest.mark.asyncio
async def test_get_all_agents(agent_manager, agent_config):
    # 创建多个代理
    await agent_manager.create_agent("test_1", "Test Agent 1", agent_config)
    await agent_manager.create_agent("test_2", "Test Agent 2", agent_config)

    agents = agent_manager.get_all_agents()
    assert len(agents) == 2
    assert any(a["id"] == "test_1" for a in agents)
    assert any(a["id"] == "test_2" for a in agents)


@pytest.mark.asyncio
async def test_stop_all_agents(agent_manager, agent_config):
    # 创建并启动多个代理
    await agent_manager.create_agent("test_1", "Test Agent 1", agent_config)
    await agent_manager.create_agent("test_2", "Test Agent 2", agent_config)

    await agent_manager.start_agent("test_1")
    await agent_manager.start_agent("test_2")

    # 停止所有代理
    await agent_manager.stop_all_agents()

    # 验证所有代理都已停止
    agents = agent_manager.get_all_agents()
    assert all(a["status"] == "inactive" for a in agents)
