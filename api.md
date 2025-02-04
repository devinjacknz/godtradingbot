# Backend API Documentation

## Market Data

### GET /v1/price/{dex}/{symbol}
Get current price from a specific DEX.
- Parameters:
  - dex: DEX name (jupiter/raydium/orca)
  - symbol: Trading pair symbol
- Response: Current price and volume data

[... rest of api.md content ...]

## Agent Management

### POST /api/v1/agents
Create a new trading agent.
- Request:
  ```json
  {
    "agent_id": "string",
    "name": "string",
    "config": {
      "strategy_type": "string",
      "parameters": {
        "riskLevel": "string",
        "tradeSize": number
      }
    }
  }
  ```
- Response: `AgentResponse` with created agent info
  ```json
  {
    "id": "string",
    "name": "string",
    "status": "inactive",
    "type": "string",
    "config": object
  }
  ```
- Supported agent types:
  - market_data: Market data collection and analysis
  - valuation: Asset valuation and pricing
  - sentiment: Market sentiment analysis
  - fundamentals: Fundamental analysis
  - technical: Technical analysis
  - risk: Risk management
  - portfolio: Portfolio management
- Error responses:
  - 400: Agent ID already exists
  - 400: Invalid configuration
  - 500: Internal server error

### GET /api/v1/agents
List all trading agents.
- Response: Array of `AgentResponse`

### GET /api/v1/agents/{agent_id}
Get specific agent details.
- Response: `AgentResponse`
- Error responses:
  - 404: Agent not found

### PUT /api/v1/agents/{agent_id}
Update agent configuration.
- Request:
  ```json
  {
    "name": "string",
    "config": {
      "strategy_type": "string",
      "parameters": object
    }
  }
  ```
- Response: `AgentResponse`
- Error responses:
  - 404: Agent not found
  - 400: Invalid configuration

### DELETE /api/v1/agents/{agent_id}
Delete an agent.
- Response: Success message
- Error responses:
  - 404: Agent not found

### POST /api/v1/agents/{agent_id}/start
Start an agent's operations.
- Response: `AgentResponse` with updated status
- Error responses:
  - 404: Agent not found
  - 500: Failed to start agent

### POST /api/v1/agents/{agent_id}/stop
Stop an agent's operations.
- Response: `AgentResponse` with updated status
- Error responses:
  - 404: Agent not found
  - 500: Failed to stop agent

### Agent Configuration Examples

#### Market Data Agent
```json
{
  "agent_id": "market_data_1",
  "name": "BTC Market Data Agent",
  "config": {
    "symbols": ["BTC/USDC"],
    "update_interval": 60,
    "data_sources": ["binance", "coinbase"]
  }
}
```

#### Sentiment Agent
```json
{
  "agent_id": "sentiment_1",
  "name": "Crypto Sentiment Agent",
  "config": {
    "symbols": ["BTC", "ETH", "SOL"],
    "update_interval": 300,
    "languages": ["en", "zh"]
  }
}
```

#### Technical Analysis Agent
```json
{
  "agent_id": "technical_1",
  "name": "Technical Analysis Agent",
  "config": {
    "symbols": ["SOL/USDC"],
    "indicators": ["RSI", "MACD", "BB"],
    "timeframes": ["1m", "5m", "15m"]
  }
}
```

#### Risk Management Agent
```json
{
  "agent_id": "risk_1",
  "name": "Portfolio Risk Agent",
  "config": {
    "max_position_size": 1000,
    "max_drawdown": 0.1,
    "risk_metrics": ["VaR", "Sharpe"]
  }
}
```

## System Health

### GET /api/v1/health
System health check endpoint.
- Response: Health status with database connectivity check

## Authentication
All endpoints except health check require Bearer token authentication.
- Token URL: /token
- Header: Authorization: Bearer {token}
