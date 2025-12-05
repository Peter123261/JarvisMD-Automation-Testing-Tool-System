"""
JarvisMD Automation Testing Tool - API Gateway
Main FastAPI application with real evaluation integration
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from jarvismd.backend.services.api_gateway.schemas import (
    EvaluationRequest,
    HealthResponse,
    CaseCountResponse,
    BenchmarksResponse,
    EvaluationJobResponse,
    JobStatusResponse,
    JobResultsResponse,
    RootResponse,
)
from jarvismd.backend.services.api_gateway.settings import settings
import os
import logging
from datetime import datetime
import sys
from pathlib import Path
from prometheus_client import start_http_server

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Import database modules using proper package imports
from jarvismd.backend.database.database import get_session, init_database
from jarvismd.backend.services.api_gateway.paths import ENV_FILE

# Load environment variables
from dotenv import load_dotenv
load_dotenv(ENV_FILE)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# OpenTelemetry setup
def setup_opentelemetry(app: FastAPI):
    """Initialize OpenTelemetry for distributed tracing"""
    try:
        # Get OTLP endpoint from environment or use default
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
        
        # Create resource with service information
        resource = Resource.create({
            SERVICE_NAME: "medbench-api",
            SERVICE_VERSION: settings.api_version,
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        })
        
        # Set up tracer provider
        trace.set_tracer_provider(TracerProvider(resource=resource))
        tracer_provider = trace.get_tracer_provider()
        
        # Export traces to OTLP collector
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True  # Use TLS in production
        )
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)
        
        # Auto-instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)
        
        # Auto-instrument SQLAlchemy (will be initialized after DB setup)
        # SQLAlchemyInstrumentor will be called after database initialization
        
        logger.info(f"✅ OpenTelemetry initialized (OTLP endpoint: {otlp_endpoint})")
    except Exception as e:
        logger.warning(f"⚠️ OpenTelemetry initialization failed: {e}. Continuing without tracing.")
        # System continues to work without OpenTelemetry

# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown with database initialization."""
    # Startup
    logger.info("🚀 JarvisMD Automation Testing Tool starting up...")
    
    try:
        # Initialize database
        db = init_database()
        logger.info("✅ Database initialized successfully")
        
        # Initialize SQLAlchemy instrumentation after database is ready
        try:
            # Get engine from the database manager instance
            if hasattr(db, 'engine'):
                SQLAlchemyInstrumentor().instrument(engine=db.engine)
                logger.info("✅ SQLAlchemy instrumentation initialized")
            else:
                logger.warning("⚠️ Database manager has no engine attribute")
        except Exception as e:
            logger.warning(f"⚠️ SQLAlchemy instrumentation failed: {e}")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    # Start Prometheus metrics HTTP server for the API process
    try:
        metrics_port = settings.api_metrics_port
        metrics_host = settings.api_metrics_host
        start_http_server(metrics_port, addr=metrics_host)
        logger.info(f"📊 Prometheus metrics server for API started on {metrics_host}:{metrics_port}")
    except Exception as e:
        logger.warning(f"⚠️ Could not start API metrics server: {e}")
    
    # Verify routes are registered after app is fully initialized
    registered_paths = {route.path for route in app.routes if hasattr(route, 'path')}
    if "/api/benchmarks" not in registered_paths:
        logger.error("❌ CRITICAL: /api/benchmarks route is NOT registered!")
        logger.error(f"Available routes: {sorted(registered_paths)}")
    else:
        logger.info("✅ /api/benchmarks route verified at startup")
    
    logger.info("✅ Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("🛑 Application shutting down...")
    logger.info("✅ Shutdown complete")

# Create FastAPI application
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
    debug=settings.debug
)

# Initialize OpenTelemetry (must be after app creation)
setup_opentelemetry(app)

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from jarvismd.backend.services.api_gateway.routes import evaluate, health, results

# Include routers using proper package imports
app.include_router(evaluate.router, prefix="/api", tags=["evaluation"])
app.include_router(health.router, prefix="/api", tags=["health"])  
app.include_router(results.router, prefix="/api", tags=["results"])

# Verify critical routes are registered (maintainable route verification)
def _verify_routes_registered():
    """Verify that critical routes are registered on the app."""
    registered_paths = {route.path for route in app.routes if hasattr(route, 'path')}
    critical_routes = [
        "/api/benchmarks",
        "/api/health",
        "/api/test/start",
    ]
    
    missing_routes = [route for route in critical_routes if route not in registered_paths]
    
    if missing_routes:
        logger.warning(f"⚠️ Missing critical routes: {missing_routes}")
        logger.info(f"📋 Registered routes: {sorted(registered_paths)}")
    else:
        logger.info(f"✅ All critical routes verified: {critical_routes}")
        if settings.debug:
            logger.debug(f"📋 Total registered routes: {len(registered_paths)}")

# Verify routes after router inclusion
_verify_routes_registered()

# Dependency to get database session
def get_db():
    """Dependency function to get database session for API endpoints."""
    db = get_session()
    try:
        yield db
    finally:
        db.close()

# ===================== API ENDPOINTS =====================

@app.get("/", response_model=RootResponse)
async def root():
    """Root endpoint with API information."""
    return RootResponse(
        message="JarvisMD Automation Testing Tool API",
        version="1.0.0",
        docs="/api/docs",
        status="operational",
        database="connected",
        timestamp=datetime.now().isoformat()
    )

# Debug endpoint for route inspection (only in debug mode)
if settings.debug:
    @app.get("/api/debug/routes")
    async def debug_routes():
        """Debug endpoint to list all registered routes (debug mode only)."""
        routes_info = []
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes_info.append({
                    "path": route.path,
                    "methods": list(route.methods) if route.methods else [],
                    "name": getattr(route, 'name', 'N/A')
                })
        return {
            "total_routes": len(routes_info),
            "routes": sorted(routes_info, key=lambda x: x["path"]),
            "benchmarks_route_exists": any(r["path"] == "/api/benchmarks" for r in routes_info)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.backend_host, port=settings.backend_port, reload=settings.reload)

# Dependency to get database session

def get_db():

    """Dependency function to get database session for API endpoints."""
    
    db = get_session()
    
    try:


        yield db

    finally:

        db.close()



# ===================== API ENDPOINTS =====================



@app.get("/", response_model=RootResponse)
async def root():

    """Root endpoint with API information."""

    return RootResponse(
        message="JarvisMD Automation Testing Tool API",
        version="1.0.0",
        docs="/api/docs",
        status="operational",
        database="connected",
        timestamp=datetime.now().isoformat()
    )


if __name__ == "__main__":


    import uvicorn


    uvicorn.run("main:app", host=settings.backend_host, port=settings.backend_port, reload=settings.reload)


    uvicorn.run("main:app", host=settings.backend_host, port=settings.backend_port, reload=settings.reload)


    uvicorn.run("main:app", host=settings.backend_host, port=settings.backend_port, reload=settings.reload)