import json
import logging
from datetime import datetime
from typing import Any, Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # Store active connections by type (trades, performance, etc.)
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "trades": set(),
            "signals": set(),
            "performance": set(),
            "agent_status": set(),
            "analysis": set(),
            "positions": set(),
            "orders": set(),
            "risk": set(),
            "limits": set(),
        }

    async def connect(self, websocket: WebSocket, connection_type: str) -> None:
        await websocket.accept()
        if connection_type not in self.active_connections:
            self.active_connections[connection_type] = set()
        self.active_connections[connection_type].add(websocket)

    def disconnect(self, websocket: WebSocket, connection_type: str) -> None:
        if connection_type in self.active_connections:
            self.active_connections[connection_type].remove(websocket)

    async def broadcast_to_type(
        self, message: Dict[str, Any], connection_type: str
    ) -> None:
        if connection_type not in self.active_connections:
            logger.warning(
                "Attempted to broadcast to unknown connection type: %s", connection_type
            )
            return

        dead_connections = set()
        for connection in self.active_connections[connection_type]:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                dead_connections.add(connection)
                logger.info(f"Client disconnected from {connection_type} channel")
            except Exception as e:
                dead_connections.add(connection)
                logger.error(
                    "Error broadcasting to %s client: %s", connection_type, str(e)
                )

        # Remove dead connections after iteration
        for dead_connection in dead_connections:
            self.active_connections[connection_type].remove(dead_connection)

    async def send_personal_message(
        self, message: Dict[str, Any], websocket: WebSocket
    ) -> None:
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            logger.info("Client disconnected during personal message")
        except Exception as e:
            logger.error(f"Error sending personal message: {str(e)}")


manager = ConnectionManager()


async def handle_websocket_connection(
    websocket: WebSocket, connection_type: str
) -> None:
    try:
        await manager.connect(websocket, connection_type)
        logger.info(f"New client connected to {connection_type} channel")
        while True:
            try:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    if isinstance(message, dict) and message.get("type") == "ping":
                        await manager.send_personal_message(
                            {
                                "type": "pong",
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                            websocket,
                        )
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON received: {str(e)}")
                    continue
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {str(e)}")
                break
    finally:
        manager.disconnect(websocket, connection_type)
        logger.info(f"Client disconnected from {connection_type} channel")


async def broadcast_trade_update(trade_data: Dict[str, Any]) -> None:
    """Broadcast trade updates to all connected clients"""
    await manager.broadcast_to_type(
        {
            "type": "trade_update",
            "data": trade_data,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "trades",
    )


async def broadcast_signal(signal_data: Dict[str, Any]) -> None:
    """Broadcast new signals to all connected clients"""
    await manager.broadcast_to_type(
        {
            "type": "new_signal",
            "data": signal_data,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "signals",
    )


async def broadcast_performance_update(performance_data: Dict[str, Any]) -> None:
    """Broadcast performance updates to all connected clients"""
    await manager.broadcast_to_type(
        {
            "type": "performance_update",
            "data": performance_data,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "performance",
    )


async def broadcast_agent_status(agent_type: str, status: str) -> None:
    """Broadcast agent status updates to all connected clients"""
    await manager.broadcast_to_type(
        {
            "type": "agent_status",
            "data": {"agent_type": agent_type, "status": status},
            "timestamp": datetime.utcnow().isoformat(),
        },
        "agent_status",
    )


async def broadcast_analysis(analysis: Dict[str, Any]) -> None:
    """Broadcast market analysis updates to all connected clients"""
    await manager.broadcast_to_type(
        {
            "type": "analysis_update",
            "data": analysis,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "analysis",
    )


async def broadcast_position_update(position: Dict[str, Any]) -> None:
    """Broadcast position updates to all connected clients"""
    await manager.broadcast_to_type(
        {
            "type": "position_update",
            "data": position,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "positions",
    )

async def broadcast_order_update(order: Dict[str, Any]) -> None:
    """Broadcast order updates to all connected clients"""
    await manager.broadcast_to_type(
        {
            "type": "order_update",
            "data": order,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "orders",
    )


async def broadcast_risk_update(metrics: Dict[str, Any]) -> None:
    """Broadcast risk metrics updates to all connected clients"""
    await manager.broadcast_to_type(
        {
            "type": "risk_update",
            "data": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "risk",
    )


async def broadcast_limit_update(limits: Dict[str, Any]) -> None:
    """Broadcast limit settings updates to all connected clients"""
    await manager.broadcast_to_type(
        {
            "type": "limit_update",
            "data": limits,
            "timestamp": datetime.utcnow().isoformat(),
        },
        "limits",
    )
