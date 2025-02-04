# Trading System API Documentation
# 交易系统 API 文档

## Core Trading Functionality (交易核心)

### Order Management (订单管理)
- POST /api/v1/orders
  - Create new order
  - 创建新订单
  - Request Body:
    ```json
    {
      "symbol": "string",
      "order_type": "market|limit",
      "direction": "buy|sell",
      "quantity": "float",
      "price": "float"
    }
    ```

- GET /api/v1/orders
  - List all orders
  - 列出所有订单

- GET /api/v1/orders/{order_id}
  - Get order details
  - 获取订单详情

### Position Management (持仓管理)
- GET /api/v1/account/positions
  - Get current positions
  - 获取当前持仓
  - Response:
    ```json
    {
      "positions": [
        {
          "symbol": "string",
          "direction": "long|short",
          "size": "float",
          "entry_price": "float",
          "current_price": "float",
          "unrealized_pnl": "float"
        }
      ]
    }
    ```

### Account Balance (账户余额)
- GET /api/v1/account/balance
  - Get account balance
  - 获取账户余额
  - Response:
    ```json
    {
      "balance": "float",
      "available": "float",
      "locked": "float"
    }
    ```

### System Monitoring (系统监控)
- GET /metrics
  - Returns Prometheus format metrics
  - 返回Prometheus格式指标
  - Content-Type: text/plain
  - Includes:
    - Model performance metrics (模型性能指标)
    - Trading system metrics (交易系统指标)
    - Risk management metrics (风险管理指标)

- GET /api/v1/monitoring/alerts
  - Returns alert history
  - 返回告警历史
  - Response:
    ```json
    {
      "alerts": [
        {
          "level": "critical|warning|info",
          "message": "string",
          "timestamp": "ISO-8601",
          "metadata": {}
        }
      ]
    }
    ```

- GET /api/v1/monitoring/audit
  - Returns system audit logs
  - 返回系统审计日志
  - Query Parameters:
    - start_time: ISO-8601
    - end_time: ISO-8601
    - user_id: string
    - severity: string
    - limit: integer
  - Response:
    ```json
    {
      "logs": [
        {
          "action": "string",
          "details": {},
          "timestamp": "ISO-8601",
          "user_id": "string",
          "severity": "string"
        }
      ]
    }
    ```

### Risk Control (风险控制)
- GET /api/v1/risk/metrics
  - Get risk metrics with AI analysis
  - 获取风险指标及AI分析
  - Response:
    ```json
    {
      "total_exposure": "float",
      "margin_used": "float",
      "margin_ratio": "float",
      "daily_pnl": "float",
      "total_pnl": "float",
      "ai_analysis": {
        "risk_level": "low|medium|high",
        "confidence": "float",
        "recommendations": ["string"]
      }
    }
    ```

### Risk Metrics (风险指标)
- GET /api/v1/risk/limits
  - Get risk limits
  - 获取风险限制
  - Response:
    ```json
    {
      "max_position_size": "float",
      "max_daily_loss": "float",
      "max_leverage": "float",
      "max_trades_per_day": "integer"
    }
    ```

### Limit Settings (限额设置)
- POST /api/v1/risk/limits
  - Update risk limits
  - 更新风险限制
  - Request Body:
    ```json
    {
      "max_position_size": "float",
      "max_daily_loss": "float",
      "max_leverage": "float",
      "max_trades_per_day": "integer"
    }
    ```

## WebSocket Endpoints (WebSocket 端点)

### Real-time Updates (实时更新)
- /ws/trades
  - Real-time trade updates
  - 实时交易更新

- /ws/positions
  - Position updates
  - 持仓更新

- /ws/orders
  - Order status updates
  - 订单状态更新

- /ws/risk
  - Risk metrics updates
  - 风险指标更新

- /ws/alerts
  - Real-time system alerts
  - 实时系统告警
  - Message Format:
    ```json
    {
      "level": "critical|warning|info",
      "message": "string",
      "timestamp": "ISO-8601",
      "metadata": {}
    }
    ```

- /ws/metrics
  - Real-time performance metrics
  - 实时性能指标
  - Message Format:
    ```json
    {
      "type": "metrics",
      "data": {
        "model_metrics": {
          "latency": "float",
          "requests_per_second": "float",
          "error_rate": "float"
        },
        "system_metrics": {
          "memory_usage": "float",
          "cpu_usage": "float",
          "active_connections": "integer"
        }
      },
      "timestamp": "ISO-8601"
    }
    ```

- /ws/analysis
  - AI analysis updates
  - AI分析更新
  - Message Format:
    ```json
    {
      "type": "ai_analysis",
      "data": {
        "symbol": "string",
        "action": "buy|sell|hold",
        "confidence": "float",
        "reasoning": "string",
        "risk_assessment": {
          "risk_reward_ratio": "float",
          "expected_return": "float",
          "market_volatility": "float",
          "position_size_recommendation": "float"
        },
        "recommendations": {
          "entry_price": "float",
          "stop_loss": "float",
          "take_profit": "float"
        }
      },
      "timestamp": "ISO-8601 datetime"
    }
    ```

### WebSocket Message Format (WebSocket 消息格式)
```json
{
  "type": "trade|position|order|risk",
  "data": {
    // Event specific data
  },
  "timestamp": "ISO-8601 datetime"
}
```

## Authentication (认证)
All API endpoints require Bearer token authentication:
所有API端点都需要Bearer令牌认证：

```
Authorization: Bearer <access_token>
```

## Rate Limits (速率限制)
- Maximum 60 requests per minute per IP
- 每个IP每分钟最多60个请求
- WebSocket connections limited to 1 per user per type
- 每个用户每种类型限制1个WebSocket连接
