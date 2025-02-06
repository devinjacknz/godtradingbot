import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import and_, text, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, select
from sqlalchemy.sql.expression import true, cast, BinaryExpression
from sqlalchemy.orm import aliased, Query, column_property
from sqlalchemy.sql.selectable import Select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import column, expression
from sqlalchemy.types import TypeDecorator, String as StringType
from sqlalchemy.sql.operators import ColumnOperators
from decimal import Decimal
from typing import Optional

from tradingbot.api.core.config import settings

def calculate_trade_profit(trade) -> float:
    """Calculate profit for a trade with proper type handling."""
    try:
        if not all([
            isinstance(trade.exit_price, (float, int, Decimal)),
            isinstance(trade.entry_price, (float, int, Decimal)),
            isinstance(trade.quantity, (float, int, Decimal))
        ]):
            return 0.0

        exit_price = float(trade.exit_price)
        entry_price = float(trade.entry_price)
        quantity = float(trade.quantity)

        return (
            (exit_price - entry_price)
            if trade.direction == "long"
            else (entry_price - exit_price)
        ) * quantity
    except (TypeError, ValueError, AttributeError):
        return 0.0
from tradingbot.api.models.trading import (
    Order,
    OrderBase,
    OrderCreate,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
    PositionStatus,
    TradeStatus,
)
from tradingbot.api.models.trade import Trade, TradeCreate
from tradingbot.api.models.risk import (
    RiskMetrics,
    LimitSettings,
    LimitSettingsUpdate,
)
from tradingbot.api.models.base import PyObjectId
from tradingbot.api.models.market import MarketData
from tradingbot.api.models.user import Account
from tradingbot.api.models.agent import Agent, AgentCreate, AgentStatus
from tradingbot.api.models.signal import Signal, SignalCreate
from tradingbot.api.models.strategy import Strategy, StrategyCreate
from tradingbot.api.core.deps import (
    get_db,
    init_db,
    init_mongodb,
    get_mongodb,
)
from tradingbot.api.routes import swap
from tradingbot.api.services.responses import (
    AccountResponse,
    AgentListResponse,
    AgentResponse,
    LimitSettingsResponse,
    OrderListResponse,
    OrderResponse,
    PerformanceResponse,
    PositionListResponse,
    RiskMetricsResponse,
    SignalListResponse,
    SignalResponse,
    StrategyListResponse,
    StrategyResponse,
    TradeListResponse,
    TradeResponse,
)
HAS_AI_MODEL = False
try:
    from tradingbot.backend.ai_model import AIModel
    HAS_AI_MODEL = True
except ImportError:
    AIModel = None
from tradingbot.api.websocket.handler import (
    broadcast_limit_update,
    broadcast_order_update,
    broadcast_performance_update,
    broadcast_position_update,
    broadcast_risk_update,
    broadcast_signal,
    broadcast_trade_update,
    handle_websocket,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    try:
        # In a real application, you would decode and verify the JWT token
        # For now, we'll return a mock user
        return {"id": "test_user", "username": "test"}
    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


import os
import asyncio
import logging
import motor.motor_asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, HTTPException
from contextlib import asynccontextmanager
from src.tradingbot.api.monitoring.service import monitoring_service
from src.tradingbot.api.core.db import init_db

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Initialize databases
        logger.info("Initializing PostgreSQL database...")
        init_db()  # Initialize PostgreSQL
        
        logger.info("Initializing MongoDB connection...")
        app.state.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
            os.getenv("MONGODB_URL", "mongodb://localhost:27017"),
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000
        )
        await app.state.mongo_client.admin.command('ping')
        app.state.db = app.state.mongo_client.tradingbot
        
        # Start monitoring service
        logger.info("Starting monitoring service...")
        from tradingbot.api.monitoring.service import monitoring_service
        await monitoring_service.start()
        
        logger.info("All services initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Service initialization error: {e}")
        raise
    finally:
        logger.info("Cleaning up services...")
        if hasattr(app.state, 'mongo_client'):
            app.state.mongo_client.close()
        await monitoring_service.stop()

app = FastAPI(lifespan=lifespan)

# Include routers
app.include_router(swap.router, prefix="/api/v1/swap", tags=["swap"])

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Market Analysis endpoint
@app.post("/api/v1/analysis")
async def analyze_market(market_data: MarketData) -> dict:
    try:
        logger.info(f"Received market data for analysis: {market_data.symbol}")
        analysis = {"status": "AI model not available"}
        if HAS_AI_MODEL and AIModel is not None:
            try:
                model = AIModel()
                analysis_request = {
                    "symbol": market_data.symbol,
                    "price": market_data.price,
                    "volume": market_data.volume,
                    "indicators": market_data.metadata.get("indicators", {}),
                }
                analysis = await model.analyze_data(analysis_request)
            except Exception as model_err:
                logger.error(f"Model error: {model_err}")
                analysis = {"status": "AI model error", "error": str(model_err)}

        try:
            db = await get_mongodb()
            await db.market_snapshots.insert_one(market_data.model_dump())
            await db.technical_analysis.insert_one(
                {
                    "symbol": market_data.symbol,
                    "timestamp": datetime.utcnow(),
                    "analysis": analysis,
                    "market_data": market_data.model_dump(),
                }
            )
        except Exception as store_err:
            logger.error(f"Storage error: {store_err}")

        return {
            "status": "success",
            "data": analysis,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Health check endpoint
@app.get("/api/v1/health")
async def health_check() -> dict:
    try:
        # Test database connection
        from sqlalchemy import text

        db = next(get_db())
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "version": "1.0.0",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


# WebSocket endpoints
@app.websocket("/ws/trades")
async def websocket_trades(websocket: WebSocket) -> None:
    await handle_websocket(websocket, "trades")


@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket) -> None:
    await handle_websocket(websocket, "signals")


@app.websocket("/ws/performance")
async def websocket_performance(websocket: WebSocket) -> None:
    await handle_websocket(websocket, "performance")


@app.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket) -> None:
    await handle_websocket(websocket, "analysis")


@app.get("/api/v1/account/balance", response_model=AccountResponse)
async def get_account_balance(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> AccountResponse:
    try:
        account = (
            db.query(Account)
            .filter(and_(Account.user_id == current_user["id"]))
            .first()
        )
        if not account:
            account = Account(user_id=current_user["id"], balance=0.0)
            db.add(account)
            db.commit()
            db.refresh(account)
        return account
    except Exception as e:
        logger.error(f"Error fetching account balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch balance")


@app.get("/api/v1/account/positions", response_model=PositionListResponse)
async def get_account_positions(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> PositionListResponse:
    try:
        positions = (
            db.query(Position).filter(Position.user_id == current_user["id"]).all()
        )
        positions_data = PositionListResponse(positions=positions)

        # Broadcast position updates via WebSocket
        for position in positions:
            await broadcast_position_update(position.model_dump())

        return positions_data
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch positions")


@app.websocket("/ws/positions")
async def websocket_positions(websocket: WebSocket) -> None:
    await handle_websocket(websocket, "positions")


@app.websocket("/ws/orders")
async def websocket_orders(websocket: WebSocket) -> None:
    await handle_websocket(websocket, "orders")


@app.post("/api/v1/orders", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> OrderResponse:
    try:
        order_data = order.model_dump()
        order_data["user_id"] = current_user["id"]
        db_order = Order(**order_data)
        db.add(db_order)
        db.commit()
        db.refresh(db_order)
        await broadcast_order_update(db_order.model_dump())
        return db_order
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail="Failed to create order")


@app.get("/api/v1/orders", response_model=OrderListResponse)
async def list_orders(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> OrderListResponse:
    try:
        orders = (
            db.query(Order)
            .filter(and_(Order.user_id == current_user["id"]))
            .all()
        )
        return OrderListResponse(orders=orders)
    except Exception as e:
        logger.error(f"Error listing orders: {e}")
        raise HTTPException(status_code=500, detail="Failed to list orders")


@app.get("/api/v1/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> OrderResponse:
    try:
        order = (
            db.query(Order)
            .filter(Order.id.isnot(None))
            .filter(Order.id == int(order_id))
            .filter(Order.user_id == str(current_user["id"]))
            .first()
        )
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch order")


@app.websocket("/ws/risk")
async def websocket_risk(websocket: WebSocket) -> None:
    await handle_websocket(websocket, "risk")


@app.get("/api/v1/risk/metrics", response_model=RiskMetricsResponse)
async def get_risk_metrics(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> RiskMetricsResponse:
    try:
        positions = (
            db.query(Position).filter(Position.user_id == current_user["id"]).all()
        )

        # Calculate risk metrics
        total_exposure = sum(abs(p.size * p.current_price) for p in positions)
        margin_used = total_exposure * 0.1  # Example: 10% margin requirement
        margin_ratio = margin_used / total_exposure if total_exposure > 0 else 0
        daily_pnl = sum(p.unrealized_pnl for p in positions)
        total_pnl = daily_pnl  # For simplicity, using same value

        # Create or update risk metrics
        risk_metrics = (
            db.query(RiskMetrics)
            .filter(RiskMetrics.user_id == current_user["id"])
            .first()
        )

        if not risk_metrics:
            risk_metrics = RiskMetrics(
                user_id=current_user["id"],
                total_exposure=total_exposure,
                margin_used=margin_used,
                margin_ratio=margin_ratio,
                daily_pnl=daily_pnl,
                total_pnl=total_pnl,
            )
            db.add(risk_metrics)
        else:
            risk_metrics.total_exposure = total_exposure
            risk_metrics.margin_used = margin_used
            risk_metrics.margin_ratio = margin_ratio
            risk_metrics.daily_pnl = daily_pnl
            risk_metrics.total_pnl = total_pnl

        db.commit()
        db.refresh(risk_metrics)
        await broadcast_risk_update(risk_metrics.model_dump())
        return risk_metrics
    except Exception as e:
        logger.error(f"Error calculating risk metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate risk metrics")


@app.post("/api/v1/risk/limits", response_model=LimitSettingsResponse)
async def update_limit_settings(
    settings: LimitSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> LimitSettingsResponse:
    try:
        limit_settings = (
            db.query(LimitSettings)
            .filter(LimitSettings.user_id == current_user["id"])
            .first()
        )

        if not limit_settings:
            limit_settings = LimitSettings(
                user_id=current_user["id"], **settings.model_dump()
            )
            db.add(limit_settings)
        else:
            for key, value in settings.model_dump().items():
                setattr(limit_settings, key, value)

        db.commit()
        db.refresh(limit_settings)
        await broadcast_limit_update(limit_settings.model_dump())
        return limit_settings
    except Exception as e:
        logger.error(f"Error updating limit settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update limits")


@app.get("/api/v1/risk/limits", response_model=LimitSettingsResponse)
async def get_limit_settings(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> LimitSettingsResponse:
    try:
        limit_settings = (
            db.query(LimitSettings)
            .filter(LimitSettings.user_id == current_user["id"])
            .first()
        )

        if not limit_settings:
            raise HTTPException(status_code=404, detail="Limit settings not found")

        return limit_settings
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching limit settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch limits")


# REST endpoints
@app.get("/api/v1/strategies", response_model=StrategyListResponse)
async def get_strategies(db: Session = Depends(get_db)) -> StrategyListResponse:
    try:
        strategies = db.query(Strategy).all()
        return StrategyListResponse(strategies=strategies)
    except Exception as e:
        logger.error(f"Error fetching strategies: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch strategies")


@app.post("/api/v1/strategies", response_model=StrategyResponse)
async def create_strategy(
    strategy: StrategyCreate, db: Session = Depends(get_db)
) -> StrategyResponse:
    try:
        db_strategy = Strategy(**strategy.model_dump())
        try:
            db.add(db_strategy)
            db.commit()
            db.refresh(db_strategy)
        except Exception as db_error:
            db.rollback()
            logger.error(f"Database error creating strategy: {db_error}")
            raise HTTPException(status_code=500, detail="Failed to create strategy")
        return db_strategy
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        raise HTTPException(status_code=500, detail="Failed to create strategy")


@app.get("/api/v1/agents", response_model=AgentListResponse)
async def list_agents(db: Session = Depends(get_db)) -> AgentListResponse:
    try:
        result = db.query(Agent.type).filter(Agent.type != None).distinct().all()
        agent_types = [row[0] for row in result]
        return AgentListResponse(agents=agent_types, count=len(agent_types))
    except Exception as e:
        logger.error(f"Error fetching agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch agents")


@app.get("/api/v1/agents/{agent_type}/status", response_model=AgentResponse)
async def get_agent_status(
    agent_type: str, db: Session = Depends(get_db)
) -> AgentResponse:
    try:
        if not agent_type:
            raise HTTPException(status_code=400, detail="Agent type is required")

        agent = (
            db.query(Agent)
            .filter(Agent.type == agent_type)
            .first()
        )
        if not agent:
            agent = Agent(type=agent_type, status=AgentStatus.STOPPED)
            try:
                db.add(agent)
                db.commit()
                db.refresh(agent)
            except Exception as db_error:
                db.rollback()
                logger.error(f"Database error creating agent: {db_error}")
                raise HTTPException(status_code=500, detail="Failed to create agent")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent status")


@app.patch("/api/v1/agents/{agent_type}/status", response_model=AgentResponse)
async def update_agent_status(
    agent_type: str, status: AgentStatus, db: Session = Depends(get_db)
) -> AgentResponse:
    try:
        if not agent_type:
            raise HTTPException(status_code=400, detail="Agent type is required")

        agent = (
            db.query(Agent)
            .filter(Agent.type == agent_type)
            .first()
        )
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_type} not found")

        agent.status = status
        agent.last_updated = datetime.utcnow()
        try:
            db.commit()
            db.refresh(agent)
        except Exception as db_error:
            db.rollback()
            logger.error(f"Database error updating agent status: {db_error}")
            raise HTTPException(status_code=500, detail="Failed to update agent status")

        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update agent status")


@app.post("/api/v1/agents/{agent_type}/start", response_model=AgentResponse)
async def start_agent(agent_type: str, db: Session = Depends(get_db)) -> AgentResponse:
    try:
        if not agent_type:
            raise HTTPException(status_code=400, detail="Agent type is required")

        agent = (
            db.query(Agent)
            .filter(Agent.type != None)
            .filter(Agent.type == agent_type)
            .first()
        )
        if not agent:
            agent = Agent(type=agent_type)
            db.add(agent)

        if agent.status == AgentStatus.RUNNING:
            return agent

        agent.status = AgentStatus.RUNNING
        agent.last_updated = datetime.utcnow()
        try:
            db.commit()
            db.refresh(agent)
        except Exception as db_error:
            db.rollback()
            logger.error(f"Database error starting agent: {db_error}")
            raise HTTPException(status_code=500, detail="Failed to start agent")

        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to start agent")


@app.post("/api/v1/agents/{agent_type}/stop", response_model=AgentResponse)
async def stop_agent(agent_type: str, db: Session = Depends(get_db)) -> AgentResponse:
    try:
        if not agent_type:
            raise HTTPException(status_code=400, detail="Agent type is required")

        agent = (
            db.query(Agent)
            .filter(Agent.type == agent_type)
            .first()
        )
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_type} not found")

        if agent.status == AgentStatus.STOPPED:
            return agent

        agent.status = AgentStatus.STOPPED
        agent.last_updated = datetime.utcnow()
        try:
            db.commit()
            db.refresh(agent)
        except Exception as db_error:
            db.rollback()
            logger.error(f"Database error stopping agent: {db_error}")
            raise HTTPException(status_code=500, detail="Failed to stop agent")

        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop agent")


@app.post("/api/v1/agents", response_model=AgentResponse)
async def create_agent(
    agent: AgentCreate, db: Session = Depends(get_db)
) -> AgentResponse:
    try:
        if not agent.type:
            raise HTTPException(status_code=400, detail="Agent type is required")

        existing_agent = (
            db.query(Agent)
            .filter(Agent.type != None)
            .filter(Agent.type == agent.type)
            .first()
        )
        if existing_agent:
            msg = f"Agent with type {agent.type} already exists"
            raise HTTPException(status_code=409, detail=msg)

        db_agent = Agent(type=agent.type, status=agent.status)
        try:
            db.add(db_agent)
            db.commit()
            db.refresh(db_agent)
        except Exception as db_error:
            db.rollback()
            logger.error(f"Database error creating agent: {db_error}")
            raise HTTPException(status_code=500, detail="Failed to create agent")

        return db_agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to create agent")


@app.delete("/api/v1/agents/{agent_type}", response_model=AgentResponse)
async def delete_agent(agent_type: str, db: Session = Depends(get_db)) -> AgentResponse:
    try:
        if not agent_type:
            raise HTTPException(status_code=400, detail="Agent type is required")

        agent = (
            db.query(Agent)
            .filter(Agent.type == agent_type)
            .first()
        )
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_type} not found")

        # Stop agent if running before deletion
        if agent.status == AgentStatus.RUNNING:
            agent.status = AgentStatus.STOPPED

        try:
            db.delete(agent)
            db.commit()
        except Exception as db_error:
            db.rollback()
            logger.error(f"Database error deleting agent: {db_error}")
            raise HTTPException(status_code=500, detail="Failed to delete agent")

        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete agent")


@app.get("/api/v1/trades", response_model=TradeListResponse)
async def get_trades(db: Session = Depends(get_db)) -> TradeListResponse:
    try:
        trades = db.query(Trade).all()
        return TradeListResponse(trades=trades)
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch trades")


@app.post("/api/v1/trades", response_model=TradeResponse)
async def create_trade(
    trade: TradeCreate, db: Session = Depends(get_db)
) -> TradeResponse:
    try:
        db_trade = Trade(**trade.model_dump())
        try:
            db.add(db_trade)
            db.commit()
            db.refresh(db_trade)
        except Exception as db_error:
            db.rollback()
            logger.error(f"Database error creating trade: {db_error}")
            raise HTTPException(status_code=500, detail="Failed to create trade")

        try:
            await broadcast_trade_update(db_trade.model_dump())
        except Exception as ws_error:
            logger.error(f"WebSocket broadcast error: {ws_error}")

        return db_trade
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating trade: {e}")
        raise HTTPException(status_code=500, detail="Failed to create trade")


@app.get("/api/v1/signals", response_model=SignalListResponse)
async def get_signals(db: Session = Depends(get_db)) -> SignalListResponse:
    try:
        signals = db.query(Signal).all()
        return SignalListResponse(signals=signals)
    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch signals")


@app.post("/api/v1/signals", response_model=SignalResponse)
async def create_signal(
    signal: SignalCreate, db: Session = Depends(get_db)
) -> SignalResponse:
    try:
        db_signal = Signal(**signal.model_dump())
        try:
            db.add(db_signal)
            db.commit()
            db.refresh(db_signal)
        except Exception as db_error:
            db.rollback()
            logger.error(f"Database error creating signal: {db_error}")
            raise HTTPException(status_code=500, detail="Failed to create signal")

        try:
            await broadcast_signal(db_signal.model_dump())
        except Exception as ws_error:
            logger.error(f"WebSocket broadcast error: {ws_error}")

        return db_signal
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating signal: {e}")
        raise HTTPException(status_code=500, detail="Failed to create signal")


@app.get("/api/v1/performance", response_model=PerformanceResponse)
async def get_performance(db: Session = Depends(get_db)) -> PerformanceResponse:
    try:
        trades = db.query(Trade).all()
        total_trades = len(trades)
        if total_trades == 0:
            performance_data = {
                "total_trades": 0,
                "profitable_trades": 0,
                "total_profit": 0.0,
                "win_rate": 0.0,
                "average_profit": 0.0,
                "max_drawdown": 0.0,
            }
            await broadcast_performance_update(performance_data)
            return PerformanceResponse(**performance_data)

        closed_trades = [t for t in trades if t.status == TradeStatus.CLOSED]
        closed_count = len(closed_trades)
        if closed_count == 0:
            performance_data = {
                "total_trades": total_trades,
                "profitable_trades": 0,
                "total_profit": 0.0,
                "win_rate": 0.0,
                "average_profit": 0.0,
                "max_drawdown": 0.0,
            }
            await broadcast_performance_update(performance_data)
            return PerformanceResponse(**performance_data)

        profits = []
        profitable_trades = 0
        total_profit = 0.0

        for trade in closed_trades:
            try:
                profit = calculate_trade_profit(trade)
                if profit == 0.0:
                    logger.warning(f"Could not calculate profit for trade {trade.id}")

                if profit > 0:
                    profitable_trades += 1
                total_profit += profit
                profits.append(profit)
            except (TypeError, AttributeError, Exception) as e:
                logger.error(f"Error calculating profit for trade {trade.id}: {e}")
                continue

        win_rate = profitable_trades / closed_count
        average_profit = total_profit / closed_count

        max_drawdown = 0.0
        peak = 0.0
        for profit in profits:
            peak = max(peak, profit)
            drawdown = peak - profit
            max_drawdown = max(max_drawdown, drawdown)

        performance_data = {
            "total_trades": total_trades,
            "profitable_trades": profitable_trades,
            "total_profit": round(total_profit, 8),
            "win_rate": round(win_rate, 4),
            "average_profit": round(average_profit, 8),
            "max_drawdown": round(max_drawdown, 8),
        }

        await broadcast_performance_update(performance_data)
        return PerformanceResponse(**performance_data)
    except Exception as e:
        logger.error(f"Error calculating performance metrics: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to calculate performance metrics"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
