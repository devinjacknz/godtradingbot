import pytest
from datetime import datetime
from src.backend.monitoring.alerts import AlertManager, AlertLevel

@pytest.fixture
def alert_manager():
    return AlertManager()

def test_alert_levels():
    manager = AlertManager()
    assert manager.alert_levels["critical"] == AlertLevel.CRITICAL
    assert manager.alert_levels["warning"] == AlertLevel.WARNING
    assert manager.alert_levels["info"] == AlertLevel.INFO

def test_singleton_instance():
    manager1 = AlertManager.get_instance()
    manager2 = AlertManager.get_instance()
    assert manager1 is manager2

@pytest.mark.asyncio
async def test_send_alert(alert_manager):
    level = "warning"
    message = "Test alert"
    metadata = {"source": "test"}
    
    try:
        await alert_manager.send_alert(level, message, metadata)
    except Exception as e:
        pytest.fail(f"send_alert raised {e}")

@pytest.mark.asyncio
async def test_send_alert_invalid_level(alert_manager):
    level = "invalid"
    message = "Test alert"
    
    try:
        await alert_manager.send_alert(level, message)
    except Exception as e:
        pytest.fail(f"send_alert raised {e}")

@pytest.mark.asyncio
async def test_send_alert_with_metadata(alert_manager):
    level = "critical"
    message = "Critical system alert"
    metadata = {
        "component": "risk_manager",
        "error_code": "ERR001",
        "details": {"threshold": 0.85}
    }
    
    try:
        await alert_manager.send_alert(level, message, metadata)
    except Exception as e:
        pytest.fail(f"send_alert raised {e}")
