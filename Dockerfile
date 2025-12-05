# Multi-stage Dockerfile for MedBench Automation Testing Tool
# Stage 1: Base Python image with dependencies
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt setup.py ./
COPY jarvismd/__init__.py jarvismd/

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install psycopg2-binary

# Stage 2: Development image
FROM base AS development

# Install development dependencies
RUN pip install pytest pytest-cov black flake8 ipython

# Copy entire project
COPY . .

# Install package in editable mode
RUN pip install -e .

# Expose ports
EXPOSE 8000 5555

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "jarvismd.backend.services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Stage 3: Production image
FROM base AS production

# Copy only necessary files
COPY jarvismd/ jarvismd/
COPY setup.py ./

# Install package
RUN pip install .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 8000 5555

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Default command
CMD ["uvicorn", "jarvismd.backend.services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

