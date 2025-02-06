#!/bin/bash
set -e

# Function to check if a process is running
check_process() {
    if ps -p $1 > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to check service health
check_service_health() {
    local port=$1
    local max_retries=5
    local retry=0
    while [ $retry -lt $max_retries ]; do
        if curl -s "http://localhost:$port/api/v1/health" | grep -q "healthy"; then
            return 0
        fi
        sleep 2
        retry=$((retry + 1))
    done
    return 1
}

# Set environment variables
export PYTHONPATH=/home/ubuntu/repos/B/src
export POSTGRES_DB=tradingbot
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=trading_postgres_pass_123
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
export MONGODB_URL="mongodb://localhost:27017/tradingbot"
export REDIS_URL="redis://localhost:6379"
export GMGN_API_KEY="${walletkey}"
export SOLANA_WALLET_KEY="${walletkey}"
export BACKUP_WALLET_KEY="${walletkey_2}"

# Install package in development mode
cd /home/ubuntu/repos/B/src/tradingbot
pip install -e . || {
    echo "Failed to install tradingbot package"
    exit 1
}

# Initialize database if needed
cd /home/ubuntu/repos/B/src/backend
python init_db.py || {
    echo "Failed to initialize database"
    exit 1
}

# Start MongoDB and Redis if not running
echo "=== Starting Required Services ===
# Kill any existing Prometheus processes
pkill -f prometheus_client || true
sleep 2"
sudo systemctl start mongod || sudo service mongod start
sudo systemctl start redis-server || sudo service redis-server start
sudo systemctl start postgresql || sudo service postgresql start
sleep 2

# Start Backend API with monitoring
echo "=== Starting Backend API with Monitoring ==="
cd /home/ubuntu/repos/B/src/backend
python3 -m uvicorn monitor:app --host 0.0.0.0 --port 8001 &
MONITOR_PID=$!

# Wait for monitor to start
if ! check_service_health 8001; then
    echo "Failed to start Monitoring Service"
    exit 1
fi
echo "Monitor service started successfully (PID: $MONITOR_PID)"

# Start Trading Service
echo "=== Starting Trading Service ==="
cd /home/ubuntu/repos/B/src/backend
python3 -m uvicorn trading:app --host 0.0.0.0 --port 8002 &
EXECUTOR_PID=$!

# Wait for trading to start
if ! check_service_health 8002; then
    echo "Failed to start Trading Service"
    kill $MONITOR_PID
    exit 1
fi
echo "Trading service started successfully (PID: $EXECUTOR_PID)"

# Start Backend API
echo "=== Starting Backend API ==="
cd /home/ubuntu/repos/B/src/backend
uvicorn main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Wait for API to start
if ! check_service_health 8000; then
    echo "Failed to start Backend API"
    kill $MONITOR_PID $EXECUTOR_PID
    exit 1
fi
echo "API service started successfully (PID: $API_PID)"

echo "=== All Services Started Successfully ==="
echo "Monitor PID: $MONITOR_PID"
echo "Executor PID: $EXECUTOR_PID"
echo "API PID: $API_PID (port 8000)"

# Keep running until interrupted
trap "kill $MONITOR_PID $EXECUTOR_PID $API_PID 2>/dev/null || true" EXIT
wait
