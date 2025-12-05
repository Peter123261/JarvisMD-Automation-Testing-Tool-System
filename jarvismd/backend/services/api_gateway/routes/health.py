"""
Health Check Routes
Provides system health monitoring and status endpoints.
"""

from fastapi import APIRouter, Depends
from datetime import datetime
import os
import psutil  # We'll add this to requirements later
from typing import Dict, Any
from sqlalchemy.orm import Session
from jarvismd.backend.services.api_gateway.schemas import HealthResponse
import sys
from pathlib import Path
import logging

# Add database imports using proper package imports
from jarvismd.backend.database.database import get_session
from jarvismd.backend.database.models import TestJob

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "JarvisMD Automation Testing Tool",
        "version": "1.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with system metrics."""
    try:
        # Check environment configuration
        openai_configured = bool(os.getenv("OPENAI_API_KEY"))
        
        # Basic system metrics
        memory_usage = psutil.virtual_memory().percent
        cpu_usage = psutil.cpu_percent(interval=1)
        disk_usage = psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent
        
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "configuration": {
                "openai_configured": openai_configured,
                "database_url": bool(os.getenv("DATABASE_URL")),
                "environment": os.getenv("LOG_LEVEL", "INFO")
            },
            "system_metrics": {
                "memory_usage_percent": round(memory_usage, 2),
                "cpu_usage_percent": round(cpu_usage, 2),
                "disk_usage_percent": round(disk_usage, 2)
            },
            "services": {
                "api_gateway": "running",
                "evaluation_service": "pending",  # Will update when we build services
                "analysis_service": "pending",
                "reporting_service": "pending"
            }
        }
        
        # Determine overall health
        if memory_usage > 90 or cpu_usage > 90 or disk_usage > 90:
            health_status["status"] = "degraded"
        
        if not openai_configured:
            health_status["status"] = "misconfigured"
            health_status["issues"] = ["OpenAI API key not configured"]
        
        return health_status
        
    except Exception as e:
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

@router.get("/health/dependencies")
async def check_dependencies():
    """Check external dependencies and services."""
    dependencies = {
        "openai_api": {
            "configured": bool(os.getenv("OPENAI_API_KEY")),
            "status": "unknown"  # Will test actual connectivity later
        },
        "database": {
            "configured": bool(os.getenv("DATABASE_URL")),
            "status": "unknown"  # Will test connection later
        },
        "redis": {
            "configured": True,  # Local Redis for development
            "status": "unknown"  # Will test connection later
        }
    }
    
    return {
        "timestamp": datetime.now().isoformat(),
        "dependencies": dependencies
    }

@router.get("/health/database", response_model=HealthResponse)
async def health_check_database():
    """Health check endpoint with database verification."""
    try:
        # Get database session
        db = get_session()
        test_jobs_count = db.query(TestJob).count()
        db.close()
        
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now().isoformat(),
            database="connected",
            total_test_jobs=test_jobs_count,
            openai_configured=bool(os.getenv("OPENAI_API_KEY"))
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now().isoformat(),
            database="disconnected",
            total_test_jobs=0,
            openai_configured=bool(os.getenv("OPENAI_API_KEY"))
        )