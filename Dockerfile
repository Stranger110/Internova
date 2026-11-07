FROM python:3.11-slim

# Labels for metadata
LABEL maintainer="INTERNOVA Satellite Mission Operations"
LABEL description="INTERNOVA High-Availability Satellite Ground Station & Live Space Imagery"

WORKDIR /app

# Install curl for container healthcheck & clean apt cache
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for optimal Docker layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application backend and frontend
COPY backend/app/ ./backend/app/
COPY frontend/ ./frontend/

# Create data directory for cache persistence
RUN mkdir -p /app/data

# High-Availability Environment Defaults
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8000
ENV SATELLITE_DATA_DIR=/app/data
ENV FRONTEND_DIR=/app/frontend
ENV NODE_ID=internova-sat-node-01

# Container Liveness Healthcheck
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

EXPOSE 8000

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
