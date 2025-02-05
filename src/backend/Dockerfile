FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Expose the port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app/src/backend
ENV DATABASE_URL=sqlite:///./tradingbot.db
ENV MONGODB_URL=sqlite:///./tradingbot_mongo.db
ENV JWT_SECRET=development-secret-key
ENV DEBUG=true

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
