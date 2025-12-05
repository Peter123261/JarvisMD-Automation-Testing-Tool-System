"""
Database Models for JarvisMD Automation Testing Tool
SQLAlchemy models for evaluations, results, and system tracking
"""

from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class TestJob(Base):
    """
    Tracks evaluation test runs with progress and status
    This is like a job queue - each test run gets one record
    """
    __tablename__ = "test_jobs"
    
    # Primary key - unique identifier for each test run
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Test configuration
    benchmark = Column(String, nullable=False)  # e.g., "appraise", "healthbench"
    model = Column(String, nullable=False)      # e.g., "gpt-4o", "gpt-4o-mini"
    total_cases = Column(Integer, nullable=False)
    
    # Progress tracking
    processed_cases = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending, running, completed, error
    
    # Timing
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    celery_task_id = Column(String, nullable=True)
    
    # Relationship: One TestJob has many EvaluationResults
    results = relationship("EvaluationResult", back_populates="test_job")

class EvaluationResult(Base):
    """
    Stores individual case evaluation results
    Each medical case evaluation gets one record here
    """
    __tablename__ = "evaluation_results"
    
    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Link to the test job this result belongs to
    test_job_id = Column(String, ForeignKey("test_jobs.id"), nullable=False)
    
    # Case identification
    case_id = Column(String, nullable=False)  # e.g., "drstrange_Day-1-Consult-1"
    doctor_name = Column(String, nullable=False)
    case_name = Column(String, nullable=False)
    
    # Evaluation scores
    total_score = Column(Float, nullable=False)  # Overall percentage score
    criteria_scores = Column(JSON)  # Individual criteria scores as JSON
    
    # AI evaluation details
    model_used = Column(String, nullable=False)
    evaluation_text = Column(Text)  # Full AI evaluation response
    processing_time = Column(Float)  # Time taken to evaluate (seconds)
    complexity_level = Column(String)  # Low/Moderate/High complexity assessment
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    
    # OpenTelemetry trace ID for distributed tracing
    trace_id = Column(String, nullable=True)  # OpenTelemetry trace ID
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    test_job = relationship("TestJob", back_populates="results")
    alerts = relationship("AlertQueue", back_populates="evaluation_result")

class SystemMetric(Base):
    """
    Tracks system performance and usage statistics
    Helps monitor how well our system is performing
    """
    __tablename__ = "system_metrics"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Metric details
    metric_name = Column(String, nullable=False)  # e.g., "avg_processing_time"
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String)  # e.g., "seconds", "percent", "count"
    
    # Context
    test_job_id = Column(String, ForeignKey("test_jobs.id"), nullable=True)
    benchmark = Column(String)
    model = Column(String)
    
    # Timing
    recorded_at = Column(DateTime, default=datetime.utcnow)

class AlertQueue(Base):
    """
    Flags cases scoring below 75% for clinician review
    Critical for identifying cases that need human attention
    """
    __tablename__ = "alert_queue"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Link to the evaluation result that triggered this alert
    evaluation_result_id = Column(String, ForeignKey("evaluation_results.id"), nullable=False)
    
    # Alert details
    alert_type = Column(String, default="low_score")  # low_score, error, etc.
    severity = Column(String, default="medium")  # low, medium, high, critical
    score = Column(Float, nullable=False)  # The score that triggered the alert
    threshold = Column(Float, default=75.0)  # The threshold that was crossed
    
    # Review status
    reviewed = Column(Boolean, default=False)
    reviewed_by = Column(String, nullable=True)  # Clinician who reviewed
    reviewed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)  # Review notes
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    evaluation_result = relationship("EvaluationResult", back_populates="alerts")

class MaintenanceReport(Base):
    """
    Stores results of automated maintenance tasks
    Provides historical tracking of system health and performance
    """
    __tablename__ = "maintenance_reports"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Report details
    report_type = Column(String, nullable=False)  # 'daily_maintenance', 'health_check', 'statistics'
    report_data = Column(JSON, nullable=False)  # Full report as JSON
    
    # Summary metrics for quick querying
    overall_status = Column(String)  # 'healthy', 'warning', 'error'
    cpu_percent = Column(Float)
    memory_percent = Column(Float)
    disk_percent = Column(Float)
    active_jobs = Column(Integer)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    task_id = Column(String)  # Celery task ID for tracking