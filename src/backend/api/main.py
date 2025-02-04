import asyncio
import logging

import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers import risk, strategy, trading
from .websocket import handle_websocket, periodic_metrics_update

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Trading Bot API",
    description="API for the AI-powered Trading Bot system",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception handler caught: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Include routers
app.include_router(trading.router)
app.include_router(strategy.router)
app.include_router(risk.router)


# WebSocket endpoints
@app.websocket("/ws/trades")
async def websocket_trades(websocket: WebSocket):
    await handle_websocket(websocket, "trades")


@app.websocket("/ws/positions")
async def websocket_positions(websocket: WebSocket):
    await handle_websocket(websocket, "positions")


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    await handle_websocket(websocket, "metrics")


@app.on_event("startup")
async def startup_event():
    # Start background tasks
    asyncio.create_task(periodic_metrics_update())


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
