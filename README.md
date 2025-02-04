# Trading Bot

A real-time trading bot application with a FastAPI backend and React frontend, supporting Solana trading platforms.

## Features

- Real-time trade execution and monitoring
- WebSocket-based live updates
- Solana wallet integration
- Performance metrics and analytics
- Customizable trading strategies
- PostgreSQL database for persistent storage
- Docker containerization
- CI/CD pipeline with GitHub Actions
- Prometheus and Grafana monitoring

## Prerequisites

Before setting up the application, ensure you have the following installed:

- Python 3.8 or higher
- Node.js 16 or higher
- npm (Node Package Manager)
- PostgreSQL 12 or higher
- Docker and Docker Compose
- Git
- GitHub CLI (for CI/CD setup)

## Quick Start

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd gotradingbot
   ```

2. Run the setup script:
   ```bash
   ./setup.sh
   ```
   This will:
   - Set up Python virtual environment
   - Install backend dependencies
   - Initialize the database
   - Install frontend dependencies
   - Create configuration files

3. Configure the application:
   - Backend configuration: `src/backend/.env`
   - Frontend configuration: `src/frontend/.env`

## API Documentation

### Market Data Endpoints
- `GET /v1/price/{dex}/{symbol}` - Get current price from specific DEX
- `GET /v1/history/{dex}/{symbol}` - Get historical price data
- `GET /api/v1/price/{symbol}` - Get current price from Pump.fun
- `GET /api/v1/historical/{symbol}` - Get historical price data from Pump.fun

### Trading Endpoints
- `POST /api/v1/orders` - Create new order
- `GET /api/v1/orders` - List all orders
- `GET /api/v1/orders/{order_id}` - Get specific order details

### Account Management
- `GET /api/v1/account/balance` - Get account balance
- `GET /api/v1/account/positions` - Get all positions

### Risk Management
- `GET /api/v1/risk/metrics` - Get risk metrics
- `GET /api/v1/risk/limits` - Get risk limit settings
- `POST /api/v1/risk/limits` - Update risk limit settings

### WebSocket Endpoints
- `/ws/market/{dex}` - Real-time market data stream
- `/ws/pump` - Real-time Pump.fun data stream
- `/ws/trades` - Real-time trade updates
- `/ws/positions` - Real-time position updates
- `/ws/orders` - Real-time order updates
- `/ws/risk` - Real-time risk metrics updates

For full API documentation, see [api.md](api.md)

## Development

### Backend Development

```bash
cd src/backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

### Frontend Development

```bash
cd src/frontend
npm run dev
```

## Docker Deployment

1. Build and run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

2. Access the application:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000

## CI/CD Pipeline

The project includes a complete CI/CD pipeline using GitHub Actions.

### Setting Up CI/CD

1. Run the CI/CD setup script:
   ```bash
   ./scripts/setup_cicd.sh
   ```
   This will:
   - Configure GitHub repository secrets
   - Set up deployment keys
   - Configure Docker Hub integration
   - Set up Slack notifications (optional)

2. Required Secrets:
   - `DOCKER_HUB_USERNAME`: Your Docker Hub username
   - `DOCKER_HUB_TOKEN`: Docker Hub access token
   - `PROD_HOST`: Production server hostname/IP
   - `PROD_USERNAME`: Production server username
   - `SSH_PRIVATE_KEY`: Deployment SSH key
   - `POSTGRES_DB`: Database name
   - `POSTGRES_USER`: Database username
   - `POSTGRES_PASSWORD`: Database password
   - `JWT_SECRET`: JWT signing key
   - `SLACK_WEBHOOK_URL`: Slack webhook URL (optional)

### Pipeline Workflow

1. **Test Stage**:
   - Runs backend tests with PostgreSQL
   - Runs frontend tests
   - Uploads coverage reports

2. **Build Stage**:
   - Builds Docker images
   - Pushes to Docker Hub
   - Uses layer caching for faster builds

3. **Deploy Stage**:
   - Pulls latest images on production server
   - Updates running containers
   - Runs database migrations
   - Verifies deployment health

4. **Notify Stage**:
   - Sends Slack notifications
   - Updates deployment status

### Manual Deployment

If needed, you can manually deploy using:
```bash
./deploy.sh
```

## Monitoring

### Prometheus Metrics

Access Prometheus metrics at:
- http://localhost:9090/metrics

Key metrics:
- HTTP request latency
- Database connection pool stats
- Trading bot performance metrics

### Grafana Dashboards

Access Grafana at http://localhost:3000 (default credentials: admin/admin)

Available dashboards:
- System Overview
- Trading Performance
- API Metrics

## Testing

### Backend Tests

```bash
cd src/backend
pytest -v
```

### Frontend Tests

```bash
cd src/frontend
npm test
```

## Project Structure

```
gotradingbot/
├── src/
│   ├── backend/
│   │   ├── main.py           # FastAPI application
│   │   ├── database.py       # Database models
│   │   ├── websocket.py      # WebSocket handlers
│   │   └── tests/            # Backend tests
│   │
│   └── frontend/
│       ├── src/              # React components
│       ├── api/              # API clients
│       └── tests/            # Frontend tests
│
├── docker-compose.yml        # Docker services configuration
├── .github/
│   └── workflows/            # GitHub Actions workflows
├── scripts/
│   └── setup_cicd.sh        # CI/CD setup script
└── README.md
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
