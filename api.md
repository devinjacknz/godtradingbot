# Backend API Documentation

## Base URL
Local Development: `http://127.0.0.1:8000`

## System Health
### GET /api/v1/health ✓
Status: Verified Working
- No authentication required
- Returns system health status and database connectivity

## Authentication
All endpoints except health check require Bearer token authentication.
- Token URL: /token
- Header: Authorization: Bearer {token}

## Market Data
### GET /v1/price/{dex}/{symbol}
Get current price from a specific DEX.
- Parameters:
  - dex: DEX name (jupiter/raydium/orca)
  - symbol: Trading pair symbol
- Response: Current price and volume data

```

## Account Management
### GET /api/v1/account/balance
- Requires authentication
- Returns account balance and status

### GET /api/v1/account/positions
- Requires authentication
- Returns current positions

## Trading Operations
### GET /api/v1/orders
- Requires authentication
- Returns list of orders

### POST /api/v1/orders
- Requires authentication
- Creates new order
- Request body:
```json
{
    "symbol": "string",
    "order_type": "market|limit",
    "direction": "buy|sell",
    "quantity": "number",
    "price": "number"
}
```

## Risk Management
### GET /api/v1/risk/metrics
- Requires authentication
- Returns current risk metrics

### GET /api/v1/risk/limits
- Requires authentication
- Returns trading limits

### PUT /api/v1/risk/limits
- Requires authentication
- Updates trading limits
- Request body:
```json
{
    "max_position_size": "number",
    "max_daily_loss": "number",
    "max_leverage": "number",
    "max_trades_per_day": "number"
}
```

## Strategy Management
### GET /api/v1/strategies ✓
Status: Verified Working
- Returns list of available trading strategies

### POST /api/v1/strategies
- Creates new trading strategy
- Request body:
```json
{
    "name": "string",
    "type": "string",
    "parameters": {},
    "status": "active|inactive"
}
```

## Agent Management ✓
Status: Verified Working (2025-02-05)

### POST /api/v1/agents
Creates a new trading agent
- Request body:
```json
{
    "type": "string"  // Type of the agent to create
}
```
- Response:
```json
{
    "type": "string",
    "id": "integer",
    "last_updated": "datetime"
}
```
- Notes:
  - Creates new agent with default status "stopped"
  - No authentication required
  - Returns agent details with creation timestamp

### DELETE /api/v1/agents/{agent_type}
Deletes an existing trading agent
- Parameters:
  - agent_type: Type of the agent to delete (string)
- Response:
```json
{
    "type": "string",
    "id": "integer",
    "last_updated": "datetime"
}
```
- Notes:
  - Completely removes agent from the system
  - Returns final state of agent before deletion

### GET /api/v1/agents
Lists all available trading agents
- Response:
```json
{
    "agents": ["string"],  // List of agent types
    "count": "integer"     // Total number of agents
}
```
- Notes:
  - Returns array of all agent types
  - Includes count for pagination/monitoring

### GET /api/v1/agents/{agent_type}/status
Gets the current status of a specific agent
- Parameters:
  - agent_type: Type of the agent to check (string)
- Response:
```json
{
    "type": "string",
    "id": "integer",
    "last_updated": "datetime"
}
```
- Notes:
  - Returns current agent state
  - Creates agent with "stopped" status if not found

### POST /api/v1/agents/{agent_type}/start
Starts trading for a specific agent
- Parameters:
  - agent_type: Type of the agent to start (string)
- Response:
```json
{
    "type": "string",
    "id": "integer",
    "last_updated": "datetime"
}
```
- Notes:
  - Activates trading operations for agent
  - Creates agent if not found
  - Updates status to "running"

### POST /api/v1/agents/{agent_type}/stop
Stops trading for a specific agent
- Parameters:
  - agent_type: Type of the agent to stop (string)
- Response:
```json
{
    "type": "string",
    "id": "integer",
    "last_updated": "datetime"
}
```
- Notes:
  - Deactivates trading operations
  - Updates status to "stopped"
  - Safe to call multiple times

## WebSocket Endpoints
Base WebSocket URL: `ws://127.0.0.1:8000`

- `/ws/trades` - Real-time trade updates
- `/ws/signals` - Trading signals
- `/ws/performance` - Performance metrics
- `/ws/agent-status` - Agent status updates
- `/ws/analysis` - Market analysis updates
- `/ws/positions` - Position updates
- `/ws/orders` - Order updates
- `/ws/risk` - Risk metrics updates

## Local Development Configuration
Required environment variables:
```
DATABASE_URL=sqlite:///./tradingbot.db
MONGODB_URL=mongodb://localhost:27017/tradingbot
JWT_SECRET=development-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
HOST=127.0.0.1
PORT=8000
DEBUG=true
WS_PING_INTERVAL=30000
WS_HEARTBEAT_TIMEOUT=60000
```

## Database Schema
- SQLite database for persistent storage
- MongoDB (optional) for market data and technical analysis
- Tables:
  - accounts
  - positions
  - orders
  - trades
  - signals
  - strategies
  - agents
  - risk_metrics
  - limit_settings
