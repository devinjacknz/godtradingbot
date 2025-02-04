import pytest
from datetime import datetime, timedelta
from src.backend.monitoring.audit_log import AuditLogger

@pytest.fixture
def audit_logger():
    return AuditLogger()

@pytest.mark.asyncio
async def test_log_action(audit_logger):
    action = "test_action"
    details = {"test_key": "test_value"}
    user_id = "test_user"
    
    result = await audit_logger.log_action(action, details, user_id)
    
    assert result["action"] == action
    assert result["details"] == details
    assert result["user_id"] == user_id
    assert isinstance(result["timestamp"], datetime)
    assert "_id" in result

@pytest.mark.asyncio
async def test_get_logs(audit_logger):
    # Create test logs
    await audit_logger.log_action(
        "test_action_1",
        {"key": "value1"},
        "user1",
        "info"
    )
    await audit_logger.log_action(
        "test_action_2",
        {"key": "value2"},
        "user2",
        "warning"
    )
    
    # Test filtering by time
    start_time = datetime.utcnow() - timedelta(minutes=1)
    end_time = datetime.utcnow() + timedelta(minutes=1)
    
    logs = await audit_logger.get_logs(
        start_time=start_time,
        end_time=end_time
    )
    assert len(logs) >= 2
    
    # Test filtering by user
    user_logs = await audit_logger.get_logs(user_id="user1")
    assert len(user_logs) >= 1
    assert all(log["user_id"] == "user1" for log in user_logs)
    
    # Test filtering by severity
    warning_logs = await audit_logger.get_logs(severity="warning")
    assert len(warning_logs) >= 1
    assert all(log["severity"] == "warning" for log in warning_logs)

@pytest.mark.asyncio
async def test_singleton_instance():
    logger1 = AuditLogger.get_instance()
    logger2 = AuditLogger.get_instance()
    assert logger1 is logger2

    # Test logging with singleton
    result = await logger1.log_action(
        "singleton_test",
        {"test": "data"}
    )
    assert result["action"] == "singleton_test"
