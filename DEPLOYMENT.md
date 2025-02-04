# Trading Bot System Deployment

## System Configuration

### Port Configuration
- Frontend: Port 80 (Nginx)
- Backend API: Port 8081
- Ollama API: Port 11434

### Service Status
- Backend Service: Active (tradingbot-backend.service)
- Nginx Service: Active
- Ollama Service: Active

### Nginx Configuration
Location: `/etc/nginx/sites-available/tradingbot`
- Frontend static files served from `/home/lumix/tradingbot/godtradingbot/src/frontend/dist`
- API proxy to backend on port 8081
- WebSocket endpoints configured for real-time trading data

### Available Models
1. deepseek-r1:8b (8.0B parameters)
2. deepseek-r1:1.5b (1.8B parameters)

### WebSocket Endpoints
- `/ws/trades` - Real-time trade updates
- `/ws/signals` - Trading signals
- `/ws/performance` - Performance metrics
- `/ws/agent_status` - Agent status updates
- `/ws/analysis` - Market analysis updates

### Health Check
- Endpoint: `/api/v1/health`
- Status: Healthy
- Database: Connected
- Version: 1.0.0

## Access
- Domain: lumix.azeusbot.com
- Server IP: 203.118.156.107

## File Permissions
- Frontend files owned by lumix:www-data with 775 permissions
- Backend service running under systemd with appropriate permissions
