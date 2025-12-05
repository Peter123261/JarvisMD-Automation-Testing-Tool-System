"""
Celery Application Configuration for MedBench Automation
Handles task queue setup, Redis connection, and worker configuration
"""

import os
import sys
from celery import Celery
from celery.signals import worker_ready, worker_shutdown
from celery.schedules import crontab
import logging

# Prometheus metrics server for worker process
from prometheus_client import start_http_server

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION

# Import Redis configuration using proper package imports
from jarvismd.backend.automation.task_queue.config.redis_config import get_redis_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_celery_app():
    """
    Create and configure Celery application with Redis backend
    """
    try:
        # Get Redis configuration
        redis_config = get_redis_config()
        
        # Get Redis URLs for Celery
        broker_url = redis_config.get_redis_url()
        result_backend = redis_config.get_redis_url()
        
        # Create Celery app
        celery_app = Celery(
            'medbench_automation',
            broker=broker_url,
            backend=result_backend
        )
        
        # Import tasks after creating the app to avoid circular imports
        try:
            # Import task modules using proper package imports
            import jarvismd.backend.automation.task_queue.tasks.evaluation_tasks
            import jarvismd.backend.automation.task_queue.tasks.maintenance_tasks
            
            # Update the task instances to use our app
            jarvismd.backend.automation.task_queue.tasks.evaluation_tasks.current_app = celery_app
            jarvismd.backend.automation.task_queue.tasks.maintenance_tasks.current_app = celery_app
            
            logger.info("✅ Task modules imported and configured successfully")
        except ImportError as e:
            logger.warning(f"⚠️ Could not import task modules: {e}")
            logger.info("Tasks will be auto-discovered when workers start")
        
        # Celery Configuration
        celery_app.conf.update(
            # Task serialization
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            
            # Task routing and execution
            task_routes={
                'backend.automation.task_queue.tasks.evaluation_tasks.*': {'queue': 'evaluation'},
                'backend.automation.task_queue.tasks.maintenance_tasks.*': {'queue': 'maintenance'},
            },
            
            # Worker configuration
            worker_prefetch_multiplier=1,
            task_acks_late=True,
            worker_max_tasks_per_child=1000,
            
            # Task timeouts
            task_soft_time_limit=300,  # 5 minutes soft limit
            task_time_limit=600,       # 10 minutes hard limit
            
            # Task retry configuration - 1 RETRY ONLY
            task_default_retry_delay=60,  # 1 minute
            task_max_retries=1,           # Maximum 1 retry (2 attempts total)
            
            # Monitoring and Event Tracking
            worker_send_task_events=True,
            task_send_sent_event=True,
            task_track_started=True,  # CRITICAL: Track when tasks start
            task_send_events=True,    # Send task events to monitor
            task_ignore_result=False, # Don't ignore results
            result_expires=3600,      # Results expire after 1 hour
            
            # Periodic Task Schedule (Celery Beat)
            beat_schedule={
                # Daily maintenance at 2 AM UTC
                'daily-maintenance-task': {
                    'task': 'maintenance_tasks.daily_maintenance',
                    'schedule': crontab(hour=2, minute=0),  # 2:00 AM daily
                    'options': {
                        'expires': 3600,  # Task expires after 1 hour if not executed
                    }
                },
                # System health check every 4 hours
                'periodic-health-check': {
                    'task': 'maintenance_tasks.system_health_check',
                    'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
                    'options': {
                        'expires': 1800,  # Expires after 30 minutes
                    }
                },
                # Worker statistics every 6 hours
                'worker-stats-collection': {
                    'task': 'maintenance_tasks.get_worker_statistics',
                    'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
                    'options': {
                        'expires': 1800,
                    }
                },
            },
        )
        
        logger.info("✅ Celery application created successfully")
        logger.info(f"🔗 Broker: {broker_url}")
        logger.info(f"💾 Backend: {result_backend}")
        logger.info("📅 Scheduled tasks configured: daily_maintenance (2 AM), health_check (every 4h), statistics (every 6h)")
        
        return celery_app
        
    except Exception as e:
        logger.error(f"❌ Failed to create Celery application: {e}")
        raise

# Create the Celery app instance
celery_app = create_celery_app()

# OpenTelemetry setup for Celery worker
def setup_opentelemetry_worker():
    """Initialize OpenTelemetry for Celery worker distributed tracing"""
    try:
        # Get OTLP endpoint from environment or use default
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
        
        # Create resource with service information
        resource = Resource.create({
            SERVICE_NAME: "medbench-celery-worker",
            SERVICE_VERSION: "1.0.0",
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
        
        logger.info(f"✅ OpenTelemetry initialized for Celery worker (OTLP endpoint: {otlp_endpoint})")
    except Exception as e:
        logger.warning(f"⚠️ OpenTelemetry initialization failed for Celery worker: {e}. Continuing without tracing.")
        # System continues to work without OpenTelemetry

# Worker lifecycle signals
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Called when worker is ready to accept tasks"""
    logger.info(f"🚀 Worker {sender} is ready to process tasks")
    
    # Initialize OpenTelemetry for the worker
    setup_opentelemetry_worker()
    
    # Start a Prometheus metrics server for the Celery worker (port 8002)
    try:
        start_http_server(8002)
        logger.info("📊 Prometheus metrics server for Celery worker started on port 8002")
    except Exception as e:
        logger.warning(f"⚠️ Could not start worker metrics server: {e}")

@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Called when worker is shutting down"""
    logger.info(f"🛑 Worker {sender} is shutting down")

# Task discovery
def get_registered_tasks():
    """Get list of registered tasks"""
    return list(celery_app.tasks.keys())

if __name__ == '__main__':
    # Test the Celery app
    print("🧪 Testing Celery Application...")
    print(f"📋 Registered tasks: {get_registered_tasks()}")
    print("✅ Celery app configuration complete!")