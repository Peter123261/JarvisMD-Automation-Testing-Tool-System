"""
Results API Routes
Handles evaluation results retrieval and analysis
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jarvismd.backend.services.api_gateway.schemas import ResultSummary
import sys
from pathlib import Path
import logging
import os
import json
from urllib.parse import quote

# Import database using proper package imports
from jarvismd.backend.database.database import get_session
from jarvismd.backend.database.models import TestJob, EvaluationResult as DBEvaluationResult, MaintenanceReport

# Create dependency for database session
def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()

# Import maintenance tasks
try:
    from jarvismd.backend.automation.task_queue.tasks.maintenance_tasks import archive_old_jobs
    MAINTENANCE_AVAILABLE = True
except ImportError:
    MAINTENANCE_AVAILABLE = False
    archive_old_jobs = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/results", tags=["results"])

@router.get("/trace/{trace_id}")
async def get_trace_url(trace_id: str):
    """
    Get trace viewing URL for a given trace ID
    
    Returns URLs for viewing the trace in different UIs (Grafana, Jaeger, etc.)
    """
    try:
        # Get base URLs from environment or settings
        grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3000")
        jaeger_url = os.getenv("JAEGER_URL", "http://localhost:16686")
        tempo_url = os.getenv("TEMPO_URL", "http://localhost:3200")
        
        # Format trace ID (remove dashes if present, ensure it's 32 hex chars)
        clean_trace_id = trace_id.replace('-', '').lower()
        if len(clean_trace_id) != 32:
            raise HTTPException(status_code=400, detail="Invalid trace ID format")
        
        # Construct Grafana Explore URL for Tempo
        # Simplest approach: Open Explore with Tempo selected
        # User can then click "Import trace" button and paste the trace ID
        # We'll include the trace ID as a query parameter for easy access
        explore_pane = ["now-1h", "now", "Tempo", {}]
        explore_json = json.dumps(explore_pane)
        # Add trace_id as a separate parameter so it's accessible
        grafana_trace_url = f"{grafana_url}/explore?orgId=1&left={quote(explore_json)}&traceId={clean_trace_id}"
        
        jaeger_trace_url = f"{jaeger_url}/trace/{clean_trace_id}"
        
        return {
            "trace_id": clean_trace_id,
            "urls": {
                "grafana": grafana_trace_url,
                "jaeger": jaeger_trace_url,
                "tempo": f"{tempo_url}/api/traces/{clean_trace_id}"
            },
            "preferred": "grafana"  # Default to Grafana since it's already integrated
        }
    except Exception as e:
        logger.error(f"❌ Failed to generate trace URL: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate trace URL: {str(e)}")

# Pydantic models for API responses
class EvaluationResult(BaseModel):
    id: str
    job_id: str
    case_id: str
    model: str
    score: float
    criteria_scores: dict
    evaluation_text: str
    timestamp: datetime
    processing_time: float
    trace_id: Optional[str] = None  # OpenTelemetry trace ID for distributed tracing

# Using ResultSummary from schemas.py instead of local definition

# Mock data storage (will be replaced with database in Day 3)
mock_results = {}

@router.get("/summary", response_model=ResultSummary)
async def get_results_summary(
    db: Session = Depends(get_db),
    job_id: Optional[str] = Query(None, description="Filter by specific job ID"),
    start_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    benchmark: Optional[str] = Query(None, description="Filter by benchmark name"),
    include_failed: bool = Query(False, description="Include failed evaluations (0.0 scores)")
):
    """
    Get summary statistics of evaluation results with flexible filtering
    
    Examples:
    - /api/results/summary (latest completed job only)
    - /api/results/summary?job_id=288ea3f2-657f-47e3-871c-72fae010bc10 (specific job)
    - /api/results/summary?start_date=2025-09-27&end_date=2025-09-28 (date range)
    - /api/results/summary?include_failed=true (include 0.0 scores)
    """
    try:
        # Build query with filters
        query = db.query(DBEvaluationResult)
        
        # Filter by job_id if provided
        if job_id:
            query = query.filter(DBEvaluationResult.test_job_id == job_id)
        # If no job_id specified, default to latest completed job
        elif not start_date and not end_date:
            # Get the most recent completed job
            latest_job = db.query(TestJob).filter(TestJob.status == "completed").order_by(TestJob.end_time.desc()).first()
            if latest_job:
                query = query.filter(DBEvaluationResult.test_job_id == latest_job.id)
        
        # Filter by date range if provided
        if start_date:
            from datetime import datetime
            start_dt = datetime.fromisoformat(start_date)
            query = query.filter(DBEvaluationResult.created_at >= start_dt)
        
        if end_date:
            from datetime import datetime
            end_dt = datetime.fromisoformat(f"{end_date}T23:59:59")
            query = query.filter(DBEvaluationResult.created_at <= end_dt)
        
        # Filter by benchmark if provided
        if benchmark:
            # Get job IDs that match the benchmark
            benchmark_job_ids = db.query(TestJob.id).filter(TestJob.benchmark == benchmark).all()
            benchmark_job_ids = [job_id[0] for job_id in benchmark_job_ids]
            if benchmark_job_ids:
                query = query.filter(DBEvaluationResult.test_job_id.in_(benchmark_job_ids))
            else:
                # No jobs found with this benchmark, return empty result
                return ResultSummary(
                    total_evaluations=0,
                    average_score=0.0,
                    benchmark=benchmark,
                    model="unknown",
                    completion_time=None,
                    cases_flagged_for_review=0,
                    review_threshold=75.0
                )
        
        # Get filtered results
        all_results = query.all()
        
        if not all_results:
            return ResultSummary(
                total_evaluations=0,
                average_score=0.0,
                benchmark="unknown",
                model="unknown",
                completion_time=None,
                cases_flagged_for_review=0,
                review_threshold=75.0
            )
        
        # Calculate flagged cases from ALL results (including failed cases with 0.0 score)
        # Failed cases (0.0) should be counted as flagged since 0.0 < 75.0
        flagged_cases = len([r for r in all_results if (r.total_score or 0.0) < 75.0])
        
        # Filter out failed evaluations (0.0 scores) for average score calculation unless explicitly requested
        if not include_failed:
            successful_results = [r for r in all_results if r.total_score > 0]
            if successful_results:
                results = successful_results
            else:
                results = all_results  # If all failed, use all results
        else:
            results = all_results
        
        # Calculate statistics (only for successful cases if include_failed=False)
        scores = [r.total_score for r in results if r.total_score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        # Get job info (use specific job if filtered, otherwise latest)
        if job_id:
            job = db.query(TestJob).filter(TestJob.id == job_id).first()
        else:
            job = db.query(TestJob).order_by(TestJob.end_time.desc()).first()
        
        benchmark = job.benchmark if job else "unknown"
        model = job.model if job else "unknown"
        completion_time = job.end_time.isoformat() if job and job.end_time else None
        
        return ResultSummary(
            total_evaluations=len(results),
            average_score=round(avg_score, 2),
            benchmark=benchmark,
            model=model,
            completion_time=completion_time,
            cases_flagged_for_review=flagged_cases,
            review_threshold=75.0
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to get results summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get results summary: {str(e)}")

@router.get("/jobs/recent")
async def get_recent_jobs(
    db: Session = Depends(get_db),
    limit: int = Query(default=10, le=50, description="Number of recent jobs to return"),
    benchmark: Optional[str] = Query(None, description="Filter by benchmark name")
):
    """
    Get list of recent evaluation jobs for easy job ID selection
    
    Returns job IDs, status, timing, and case counts for easy copy/paste
    """
    try:
        query = db.query(TestJob)
        
        # Filter by benchmark if provided
        if benchmark:
            query = query.filter(TestJob.benchmark == benchmark)
        
        jobs = query.order_by(TestJob.start_time.desc()).limit(limit).all()
        
        result = []
        for job in jobs:
            # Count evaluations for this job
            eval_count = db.query(DBEvaluationResult).filter(DBEvaluationResult.test_job_id == job.id).count()
            successful_count = db.query(DBEvaluationResult).filter(
                DBEvaluationResult.test_job_id == job.id,
                DBEvaluationResult.total_score > 0
            ).count()
            
            result.append({
                "job_id": job.id,
                "status": job.status,
                "benchmark": job.benchmark,
                "model": job.model,
                "total_cases": job.total_cases,
                # Show what the UI really cares about: how many case rows exist for this job.
                # Using DB count avoids stale/missing values in job.processed_cases.
                "processed_cases": eval_count,
                "successful_evaluations": successful_count,
                "failed_evaluations": eval_count - successful_count,
                "start_time": job.start_time.isoformat() if job.start_time else None,
                "end_time": job.end_time.isoformat() if job.end_time else None,
                "duration_minutes": round((job.end_time - job.start_time).total_seconds() / 60, 2) if job.end_time and job.start_time else None
            })
        
        return {
            "recent_jobs": result,
            "total_jobs": len(result),
            "usage_examples": [
                "curl http://localhost:8000/api/results/summary (latest completed job)",
                f"curl http://localhost:8000/api/results/summary?job_id={result[0]['job_id']}" if result else "No jobs available",
                "curl http://localhost:8000/api/results/summary?start_date=2025-09-27&end_date=2025-09-28"
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get recent jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get recent jobs: {str(e)}")

@router.get("/")
async def get_all_results(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    min_score: Optional[float] = Query(default=None, ge=0, le=100),
    db: Session = Depends(get_db)
) -> List[EvaluationResult]:
    """Get all evaluation results with pagination and filtering"""
    try:
        # Query real database
        query = db.query(DBEvaluationResult)
        
        # Filter by minimum score if provided
        if min_score is not None:
            query = query.filter(DBEvaluationResult.total_score >= min_score)
        
        # Apply pagination and ordering
        results = query.order_by(DBEvaluationResult.created_at.desc()).offset(offset).limit(limit).all()
        
        # Convert to API response format
        api_results = []
        for result in results:
            eval_result = EvaluationResult(
                id=result.id,
                job_id=result.test_job_id,
                case_id=result.case_id,
                model=result.model_used,
                score=result.total_score,
                criteria_scores=result.criteria_scores or {},
                evaluation_text=result.evaluation_text or "",
                timestamp=result.created_at,
                processing_time=result.processing_time,
                trace_id=result.trace_id  # Include OpenTelemetry trace ID
            )
            api_results.append(eval_result)
        
        return api_results
        
    except Exception as e:
        logger.error(f"Error fetching all results: {e}")
        return []

@router.get("/{result_id}")
async def get_result_by_id(result_id: str, db: Session = Depends(get_db)) -> EvaluationResult:
    """Get specific evaluation result by ID"""
    try:
        result = db.query(DBEvaluationResult).filter(DBEvaluationResult.id == result_id).first()
        
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        
        # Convert to API response format
        eval_result = EvaluationResult(
            id=result.id,
            job_id=result.job_id,
            case_id=result.case_id,
            doctor_name="Unknown",  # Not stored in current schema
            case_name=result.case_id,  # Use case_id as case_name
            score=result.total_score,
            criteria_scores=result.detailed_scores or {},
            processing_time=result.processing_time,
            timestamp=result.created_at,
            flagged_for_review=result.total_score < 75.0,
            review_priority="high" if result.total_score < 50.0 else "medium"
        )
        
        return eval_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching result {result_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/job/{job_id}")
async def get_results_by_job(job_id: str, db: Session = Depends(get_db)) -> List[EvaluationResult]:
    """Get all results for a specific evaluation job"""
    try:
        # Query real database for job results
        results = db.query(DBEvaluationResult).filter(
            DBEvaluationResult.test_job_id == job_id
        ).order_by(DBEvaluationResult.created_at).all()
        
        if not results:
            raise HTTPException(status_code=404, detail="No results found for this job")
        
        # Convert to API response format
        job_results = []
        for result in results:
            eval_result = EvaluationResult(
                id=result.id,
                job_id=result.test_job_id,
                case_id=result.case_id,
                model=result.model_used,
                score=result.total_score,
                criteria_scores=result.criteria_scores or {},
                evaluation_text=result.evaluation_text or "",
                timestamp=result.created_at,
                processing_time=result.processing_time,
                trace_id=result.trace_id  # Include OpenTelemetry trace ID
            )
            job_results.append(eval_result)
        
        return job_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching results for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/alerts/low-scores")
async def get_low_scoring_cases(
    threshold: float = Query(default=75.0),
    db: Session = Depends(get_db)
) -> List[EvaluationResult]:
    """Get cases scoring below threshold (for clinician review)"""
    try:
        # Query real database for low-scoring cases
        low_scoring_results = db.query(DBEvaluationResult).filter(
            DBEvaluationResult.total_score < threshold
        ).all()
        
        # Convert to API response format
        low_scoring = []
        for result in low_scoring_results:
            eval_result = EvaluationResult(
                id=result.id,
                job_id=result.test_job_id,
                case_id=result.case_id,
                model=result.model_used,
                score=result.total_score,
                criteria_scores=result.criteria_scores or {},
                evaluation_text=result.evaluation_text or "",
                timestamp=result.created_at,
                processing_time=result.processing_time,
                trace_id=result.trace_id  # Include OpenTelemetry trace ID
            )
            low_scoring.append(eval_result)
        
        # Sort by score (lowest first) for priority review
        return sorted(low_scoring, key=lambda x: x.score)
        
    except Exception as e:
        logger.error(f"Error fetching low-scoring cases: {e}")
        return []

@router.delete("/{result_id}")
async def delete_result(result_id: str):
    """Delete a specific evaluation result"""
    if result_id not in mock_results:
        raise HTTPException(status_code=404, detail="Result not found")
    
    del mock_results[result_id]
    return {"message": f"Result {result_id} deleted successfully"}

@router.post("/admin/archive-old-jobs")
async def archive_old_jobs_endpoint(days_old: int = Query(default=3, ge=0, le=365, description="Archive jobs older than this many days (0 = all completed jobs)")):
    """
    Archive completed jobs older than specified days (Manual trigger only)
    
    This endpoint provides a summary of jobs that would be archived.
    Jobs are NOT deleted - only marked for archival tracking.
    
    Args:
        days_old: Archive jobs older than this many days (default: 3)
        
    Returns:
        Summary of archived jobs
        
    Security:
        - Manual trigger only (no automatic scheduling)
        - Only completed jobs are archived
        - Data is preserved (not deleted)
        - Audit trail maintained
    """
    try:
        if not MAINTENANCE_AVAILABLE or not archive_old_jobs:
            raise HTTPException(
                status_code=503, 
                detail="Archival service not available"
            )
        
        logger.info(f"📦 Manual archival requested for jobs older than {days_old} days")
        
        # Run archival task
        result = archive_old_jobs.delay(days_old=days_old)
        
        # Wait for result (synchronous for admin operations)
        archive_summary = result.get(timeout=30)
        
        return {
            "success": True,
            "message": f"Archival completed for jobs older than {days_old} days",
            "timestamp": datetime.now().isoformat(),
            "details": archive_summary
        }
        
    except Exception as e:
        logger.error(f"❌ Archival failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Archival failed: {str(e)}"
        )

@router.get("/admin/maintenance-reports")
async def get_maintenance_reports(
    db: Session = Depends(get_db),
    report_type: Optional[str] = Query(None, description="Filter by report type: daily_maintenance, health_check, statistics"),
    limit: int = Query(10, ge=1, le=100, description="Number of reports to retrieve")
):
    """
    Get recent maintenance reports
    
    Args:
        report_type: Filter by specific report type (optional)
        limit: Number of reports to return (default: 10)
        
    Returns:
        List of maintenance reports ordered by most recent
    """
    try:
        query = db.query(MaintenanceReport)
        
        if report_type:
            query = query.filter(MaintenanceReport.report_type == report_type)
        
        reports = query.order_by(MaintenanceReport.created_at.desc()).limit(limit).all()
        
        return {
            "success": True,
            "total_reports": len(reports),
            "reports": [
                {
                    "id": r.id,
                    "report_type": r.report_type,
                    "overall_status": r.overall_status,
                    "cpu_percent": r.cpu_percent,
                    "memory_percent": r.memory_percent,
                    "disk_percent": r.disk_percent,
                    "active_jobs": r.active_jobs,
                    "created_at": r.created_at.isoformat(),
                    "task_id": r.task_id,
                    "report_data": r.report_data
                }
                for r in reports
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get maintenance reports: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get maintenance reports: {str(e)}"
        )

@router.get("/admin/maintenance-reports/latest")
async def get_latest_maintenance_report(db: Session = Depends(get_db)):
    """
    Get the most recent maintenance report (quick health check)
    
    Returns:
        Latest maintenance report with system health status
    """
    try:
        latest_report = db.query(MaintenanceReport).order_by(
            MaintenanceReport.created_at.desc()
        ).first()
        
        if not latest_report:
            return {
                "success": False,
                "message": "No maintenance reports found yet"
            }
        
        return {
            "success": True,
            "report": {
                "id": latest_report.id,
                "report_type": latest_report.report_type,
                "overall_status": latest_report.overall_status,
                "system_metrics": {
                    "cpu_percent": latest_report.cpu_percent,
                    "memory_percent": latest_report.memory_percent,
                    "disk_percent": latest_report.disk_percent
                },
                "active_jobs": latest_report.active_jobs,
                "created_at": latest_report.created_at.isoformat(),
                "full_report": latest_report.report_data
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get latest report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get latest report: {str(e)}"
        )