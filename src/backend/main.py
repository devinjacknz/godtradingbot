import logging
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import settings
from database import (
    Agent,
    AgentStatus,
    Signal,
    Strategy,
    Trade,
    TradeStatus,
    async_mongodb,
    get_db,
    init_db,
    init_mongodb,
)
from schemas import (
    AgentResponse,
    MarketData,
    PerformanceResponse,
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
from shared.models.ollama import OllamaModel
from websocket import (
    broadcast_agent_status,
    broadcast_performance_update,
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
    # Allow all origins in development
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize databases
@app.on_event("startup")
async def startup_event():
    init_db()  # Initialize PostgreSQL
    init_mongodb()  # Initialize MongoDB collections


# Market Analysis endpoint
@app.post("/api/v1/analysis")
async def analyze_market(market_data: MarketData):
    try:
        logger.info(f"Received market data for analysis: {market_data.symbol}")
        model = OllamaModel()
        analysis_request = {
            "symbol": market_data.symbol,
            "price": market_data.price,
            "volume": market_data.volume,
            "indicators": market_data.metadata.get("indicators", {}),
        }
        try:
            analysis = await model.analyze_market(analysis_request)
        except Exception as model_err:
            logger.error(f"Model error: {model_err}")
            raise HTTPException(status_code=500, detail="Market analysis failed")

        try:
            await async_mongodb.market_snapshots.insert_one(market_data.dict())
            await async_mongodb.technical_analysis.insert_one(
                {
                    "symbol": market_data.symbol,
                    "timestamp": datetime.utcnow(),
                    "analysis": analysis,
                    "market_data": market_data.dict(),
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
async def health_check():
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
async def websocket_trades(websocket: WebSocket):
    await handle_websocket_connection(websocket, "trades")


@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    await handle_websocket_connection(websocket, "signals")


@app.websocket("/ws/performance")
async def websocket_performance(websocket: WebSocket):
    await handle_websocket_connection(websocket, "performance")


@app.websocket("/ws/agent_status")
async def websocket_agent_status(websocket: WebSocket):
    await handle_websocket_connection(websocket, "agent_status")


@app.websocket("/ws/analysis")
async def websocket_analysis(websocket: WebSocket):
    await handle_websocket_connection(websocket, "analysis")


# REST endpoints
@app.get("/api/v1/strategies", response_model=StrategyListResponse)
async def get_strategies(db: Session = Depends(get_db)):
    try:
        strategies = db.query(Strategy).all()
        return StrategyListResponse(strategies=strategies)
    except Exception as e:
        logger.error(f"Error fetching strategies: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch strategies")


@app.post("/api/v1/strategies", response_model=StrategyResponse)
async def create_strategy(strategy: StrategyCreate, db: Session = Depends(get_db)):
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


@app.get("/api/v1/agents/{agent_type}/status", response_model=AgentResponse)
async def get_agent_status(agent_type: str, db: Session = Depends(get_db)):
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


@app.post("/api/v1/agents/{agent_type}/start", response_model=AgentResponse)
async def start_agent(agent_type: str, db: Session = Depends(get_db)):
    try:
        if not agent_type:
            raise HTTPException(status_code=400, detail="Agent type is required")

        agent = db.query(Agent).filter(Agent.type == agent_type).first()
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

        await broadcast_agent_status(agent_type, "running")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to start agent")


@app.post("/api/v1/agents/{agent_type}/stop", response_model=AgentResponse)
async def stop_agent(agent_type: str, db: Session = Depends(get_db)):
    try:
        if not agent_type:
            raise HTTPException(status_code=400, detail="Agent type is required")

        agent = db.query(Agent).filter(Agent.type == agent_type).first()
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

        await broadcast_agent_status(agent_type, "stopped")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop agent")


@app.get("/api/v1/trades", response_model=TradeListResponse)
async def get_trades(db: Session = Depends(get_db)):
    try:
        trades = db.query(Trade).all()
        return TradeListResponse(trades=trades)
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch trades")


@app.post("/api/v1/trades", response_model=TradeResponse)
async def create_trade(trade: TradeCreate, db: Session = Depends(get_db)):
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
async def get_signals(db: Session = Depends(get_db)):
    try:
        signals = db.query(Signal).all()
        return SignalListResponse(signals=signals)
    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch signals")


@app.post("/api/v1/signals", response_model=SignalResponse)
async def create_signal(signal: SignalCreate, db: Session = Depends(get_db)):
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
async def get_performance(db: Session = Depends(get_db)):
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
                profit = (
                    (trade.exit_price - trade.entry_price)
                    if trade.direction == "long"
                    else (trade.entry_price - trade.exit_price)
                ) * trade.quantity
                if profit > 0:
                    profitable_trades += 1
                total_profit += profit
                profits.append(profit)
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
