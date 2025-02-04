import pytest
from fastapi.testclient import TestClient

from ..main import app
from ..routes.agent_routes import agent_manager

client = TestClient(app)


@pytest.fixture
def test_agent_data():
    return {
        "agent_id": "test_agent_1",
        "name": "Test Trading Agent",
        "config": {
            "strategy_type": "momentum",
            "parameters": {"riskLevel": "medium", "tradeSize": 5},
        },
    }


@pytest.fixture(autouse=True)
async def cleanup():
    yield
    # 测试后清理所有代理
    await agent_manager.stop_all_agents()
    agent_manager.agents.clear()


def test_create_agent(test_agent_data):
    response = client.post("/api/v1/agents", json=test_agent_data)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_agent_data["agent_id"]
    assert data["name"] == test_agent_data["name"]
    assert data["status"] == "inactive"


def test_create_duplicate_agent(test_agent_data):
    # 首次创建应该成功
    response = client.post("/api/v1/agents", json=test_agent_data)
    assert response.status_code == 200

    # 重复创建应该失败
    response = client.post("/api/v1/agents", json=test_agent_data)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_agent(test_agent_data):
    # 先创建代理
    client.post("/api/v1/agents", json=test_agent_data)

    # 获取存在的代理
    response = client.get(f"/api/v1/agents/{test_agent_data['agent_id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_agent_data["agent_id"]

    # 获取不存在的代理
    response = client.get("/api/v1/agents/non_existent")
    assert response.status_code == 404


def test_list_agents(test_agent_data):
    # 创建多个代理
    client.post("/api/v1/agents", json=test_agent_data)

    test_agent_data["agent_id"] = "test_agent_2"
    client.post("/api/v1/agents", json=test_agent_data)

    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert any(a["id"] == "test_agent_1" for a in data)
    assert any(a["id"] == "test_agent_2" for a in data)


def test_update_agent(test_agent_data):
    # 先创建代理
    client.post("/api/v1/agents", json=test_agent_data)

    # 更新配置
    update_data = {
        "name": "Updated Agent",
        "config": {
            "strategy_type": "scalping",
            "parameters": {"riskLevel": "high", "tradeSize": 10},
        },
    }

    response = client.put(
        f"/api/v1/agents/{test_agent_data['agent_id']}", json=update_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Agent"
    assert data["strategy_type"] == "scalping"

    # 更新不存在的代理
    response = client.put("/api/v1/agents/non_existent", json=update_data)
    assert response.status_code == 404


def test_delete_agent(test_agent_data):
    # 先创建代理
    client.post("/api/v1/agents", json=test_agent_data)

    # 删除代理
    response = client.delete(f"/api/v1/agents/{test_agent_data['agent_id']}")
    assert response.status_code == 200

    # 确认代理已被删除
    response = client.get(f"/api/v1/agents/{test_agent_data['agent_id']}")
    assert response.status_code == 404

    # 删除不存在的代理
    response = client.delete("/api/v1/agents/non_existent")
    assert response.status_code == 404


def test_start_stop_agent(test_agent_data):
    # 先创建代理
    client.post("/api/v1/agents", json=test_agent_data)

    # 启动代理
    response = client.post(f"/api/v1/agents/{test_agent_data['agent_id']}/start")
    assert response.status_code == 200

    # 验证代理状态
    response = client.get(f"/api/v1/agents/{test_agent_data['agent_id']}")
    assert response.json()["status"] == "active"

    # 停止代理
    response = client.post(f"/api/v1/agents/{test_agent_data['agent_id']}/stop")
    assert response.status_code == 200

    # 验证代理状态
    response = client.get(f"/api/v1/agents/{test_agent_data['agent_id']}")
    assert response.json()["status"] == "inactive"

    # 测试不存在的代理
    response = client.post("/api/v1/agents/non_existent/start")
    assert response.status_code == 404


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
