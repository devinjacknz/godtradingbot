import os
import sys
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

<<<<<<< HEAD
# Add src/backend to Python path
backend_dir = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
||||||| ff2171ff6
# Add src/backend to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
=======
# Add project root to Python path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
>>>>>>> origin/main

from src.backend.database import Base, get_db  # noqa: E402
from src.backend.main import app  # noqa: E402


# Create in-memory SQLite database for testing
@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """Creates a new database session for each test function"""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Creates a new FastAPI TestClient with the test database session"""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_db(db_session):
    """Provides a database session for tests that need direct database access"""
    yield db_session


# WebSocket test client
@pytest.fixture(scope="function")
def websocket_client(client):
    """Creates a WebSocket test client"""

    class WSTestClient:
        def __init__(self, client):
            self.client = client
            self.websocket: Optional[WebSocket] = None

        async def connect(self, url: str):
            self.websocket = await self.client.websocket_connect(url)
            return self.websocket

        async def send_json(self, data: dict):
            if not self.websocket:
                raise RuntimeError("WebSocket not connected")
            await self.websocket.send_json(data)

        async def receive_json(self):
            if not self.websocket:
                raise RuntimeError("WebSocket not connected")
            return await self.websocket.receive_json()

        async def close(self):
            if self.websocket:
                await self.websocket.close()

    return WSTestClient(client)


# Sample data fixtures
@pytest.fixture
def sample_trade_data():
    return {
        "symbol": "BTC/USD",
        "direction": "long",
        "entry_time": "2025-02-02T10:00:00",
        "entry_price": 50000.0,
        "quantity": 1.0,
    }


@pytest.fixture
def sample_signal_data():
    return {
        "timestamp": "2025-02-02T10:00:00",
        "direction": "long",
        "confidence": 0.85,
        "indicators": {"rsi": 70, "macd": 1.5},
    }


@pytest.fixture
def sample_strategy_data():
    return {
        "name": "Test Strategy",
        "type": "momentum",
        "parameters": {"rsi_period": 14, "rsi_overbought": 70, "rsi_oversold": 30},
        "status": "active",
    }


# Mock WebSocket connection manager
@pytest.fixture
def mock_connection_manager(mocker):
    class MockConnectionManager:
        async def connect(self, websocket, connection_type):
            pass

        async def disconnect(self, websocket, connection_type):
            pass

        async def broadcast_to_type(self, message, connection_type):
            pass

        async def send_personal_message(self, message, websocket):
            pass

    return MockConnectionManager()


# Environment variables for testing
@pytest.fixture(autouse=True)
def env_setup(monkeypatch):
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("POSTGRES_DB", "tradingbot_test")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "postgres")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
