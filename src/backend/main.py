import logging
from datetime import datetime
from typing import List

from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import settings
from database import (
    Account,
    Agent,
    AgentStatus,
    Base,
    LimitSettings,
    Order,
    Position,
    RiskMetrics,
    Signal,
    Strategy,
    Trade,
    TradeStatus,
    async_mongodb,
    engine,
    get_db,
)
from schemas import (
    AccountResponse,
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    LimitSettingsResponse,
    LimitSettingsUpdate,
    MarketData,
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    PerformanceResponse,
    PositionListResponse,
    PositionResponse,
    RiskMetricsResponse,
    SignalCreate,
    SignalListResponse,
    SignalResponse,
    StrategyCreate,
    StrategyListResponse,
    StrategyResponse,
    TradeCreate,
    TradeListResponse,
    TradeResponse,
)
from websocket import (
    broadcast_limit_update,
    broadcast_order_update,
    broadcast_performance_update,
    broadcast_position_update,
    broadcast_risk_update,
    broadcast_signal,
    broadcast_trade_update,
    handle_websocket_connection,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize databases
@app.on_event("startup")
async def startup_event() -> None:
    try:
        Base.metadata.create_all(bind=engine)  # Initialize SQLite tables
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        # Continue even if database init fails
        pass


# Market Analysis endpoint
@app.post("/api/v1/analysis")
async def analyze_market(market_data: MarketData) -> dict:
    try:
        logger.info(f"Received market data for analysis: {market_data.symbol}")
        # Store market data
        try:
            await async_mongodb.market_snapshots.insert_one(market_data.dict())
        except Exception as store_err:
            logger.error(f"Storage error: {store_err}")

        return {
            "status": "success",
            "data": {"message": "Market data stored successfully"},
            "timestamp": datetime.utcnow().isoformat(),
        }
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
    await handle_websocket_connection(websocket, "trades")


@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket) -> None:
    await handle_websocket_connection(websocket, "signals")


@app.websocket("/ws/performance")
async def websocket_performance(websocket: WebSocket) -> None:
    await handle_websocket_connection(websocket, "performance")


@app.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket) -> None:
    await handle_websocket_connection(websocket, "analysis")


@app.get("/api/v1/account/balance", response_model=AccountResponse)
async def get_account_balance(
    db: Session = Depends(get_db)
) -> AccountResponse:
    try:
        account = db.query(Account).first()
        if not account:
            account = Account(balance=0.0)
            db.add(account)
            db.commit()
            db.refresh(account)
        return account
    except Exception as e:
        logger.error(f"Error fetching account balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch balance")


@app.get("/api/v1/account/positions", response_model=PositionListResponse)
async def get_account_positions(
    db: Session = Depends(get_db)
) -> PositionListResponse:
    try:
        positions = db.query(Position).all()
        position_responses = [PositionResponse(**p.__dict__) for p in positions]
        return PositionListResponse(positions=position_responses)
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch positions")


@app.websocket("/ws/positions")
async def websocket_positions(websocket: WebSocket) -> None:
    await handle_websocket_connection(websocket, "positions")


@app.websocket("/ws/orders")
async def websocket_orders(websocket: WebSocket) -> None:
    await handle_websocket_connection(websocket, "orders")


@app.post("/api/v1/orders", response_model=OrderResponse)
async def create_order(
    order: OrderCreate,
    db: Session = Depends(get_db)
) -> OrderResponse:
    try:
        order_data = order.model_dump()
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
    db: Session = Depends(get_db)
) -> OrderListResponse:
    try:
        orders = db.query(Order).all()
        order_responses = [OrderResponse(**o.__dict__) for o in orders]
        return OrderListResponse(orders=order_responses)
    except Exception as e:
        logger.error(f"Error listing orders: {e}")
        raise HTTPException(status_code=500, detail="Failed to list orders")


@app.get("/api/v1/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: Session = Depends(get_db)
) -> OrderResponse:
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
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
    await handle_websocket_connection(websocket, "risk")


@app.get("/api/v1/risk/metrics", response_model=RiskMetricsResponse)
async def get_risk_metrics(
    db: Session = Depends(get_db)
) -> RiskMetricsResponse:
    try:
        positions = db.query(Position).all()
        
        # Calculate risk metrics
        total_exposure = sum(abs(p.quantity * p.entry_price) for p in positions)
        margin_used = sum(p.margin_required for p in positions if p.margin_required)
        margin_ratio = margin_used / total_exposure if total_exposure > 0 else 0
        
        # Calculate PnL
        today = datetime.utcnow().date()
        daily_trades = (
            db.query(Trade)
            .filter(Trade.timestamp >= today)
            .all()
        )
        daily_pnl = sum(t.pnl for t in daily_trades if t.pnl)
        total_pnl = sum(t.pnl for t in daily_trades if t.pnl)

        # Create or update risk metrics
        risk_metrics = db.query(RiskMetrics).first()

        if not risk_metrics:
            risk_metrics = RiskMetrics(
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
    db: Session = Depends(get_db)
) -> LimitSettingsResponse:
    try:
        limit_settings = db.query(LimitSettings).first()

        if not limit_settings:
            limit_settings = LimitSettings(**settings.model_dump())
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
    db: Session = Depends(get_db)
) -> LimitSettingsResponse:
    try:
        limit_settings = db.query(LimitSettings).first()

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
        strategy_responses = [StrategyResponse(**s.__dict__) for s in strategies]
        return StrategyListResponse(strategies=strategy_responses)
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
        agents = db.query(Agent.type).distinct().all()
        agent_types = [agent[0] for agent in agents]
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

        agent = db.query(Agent).filter(Agent.type == agent_type).first()
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

        agent = db.query(Agent).filter(Agent.type == agent_type).first()
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

        agent = db.query(Agent).filter(Agent.type == agent_type).first()
        if not agent:
            agent = Agent(type=agent_type)
            db.add(agent)

        if str(agent.status) == str(AgentStatus.RUNNING):
            return agent

        db.query(Agent).filter(Agent.id == agent.id).update(
            {"status": AgentStatus.RUNNING}
        )
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

        agent = db.query(Agent).filter(Agent.type == agent_type).first()
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_type} not found")

        if str(agent.status) == str(AgentStatus.STOPPED):
            return agent

        db.query(Agent).filter(Agent.id == agent.id).update(
            {"status": AgentStatus.STOPPED}
        )
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

        existing_agent = db.query(Agent).filter(Agent.type == agent.type).first()
        if existing_agent:
            msg = f"Agent with type {agent.type} already exists"
            raise HTTPException(status_code=409, detail=msg)

        db_agent = Agent(type=agent.type, status=AgentStatus.STOPPED)
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

        agent = db.query(Agent).filter(Agent.type == agent_type).first()
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
        trade_responses = [
            TradeResponse(
                **{k: v for k, v in t.__dict__.items() if not k.startswith("_")}
            )
            for t in trades
        ]
        return TradeListResponse(trades=trade_responses)
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
        signal_responses = [
            SignalResponse(
                **{k: v for k, v in s.__dict__.items() if not k.startswith("_")}
            )
            for s in signals
        ]
        return SignalListResponse(signals=signal_responses)
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

        closed_trades = [t for t in trades if str(t.status) == str(TradeStatus.CLOSED)]
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
                exit_price = float(getattr(trade, "exit_price", 0))
                entry_price = float(getattr(trade, "entry_price", 0))
                direction = str(getattr(trade, "direction", ""))
                quantity = float(getattr(trade, "quantity", 0))

                profit = (
                    (exit_price - entry_price)
                    if direction == "long"
                    else (entry_price - exit_price)
                ) * quantity

                profit_value = float(profit)
                if profit_value > 0:
                    profitable_trades += 1
                total_profit += profit_value
                profits.append(profit_value)
            except (TypeError, AttributeError) as e:
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
            "total_profit": float(f"{total_profit:.8f}"),
            "win_rate": float(f"{win_rate:.4f}"),
            "average_profit": float(f"{average_profit:.8f}"),
            "max_drawdown": float(f"{max_drawdown:.8f}"),
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
