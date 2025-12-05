"""
Optimized Evaluation Routes for JarvisMD Automation Testing Tool
Uses the new EvaluationEngine for cost-efficient LLM evaluation
"""
# pylint: disable=import-error
# type: ignore

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import math

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends  # type: ignore
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import requests

# Import the new optimized engine using proper package import
from jarvismd.backend.services.api_gateway.evaluation_engine import evaluation_engine, get_evaluation_metrics, get_prometheus_metrics, reset_evaluation_metrics

# Import existing schemas and database using proper package imports
from jarvismd.backend.database.database import get_session
from jarvismd.backend.database.models import TestJob, EvaluationResult
from jarvismd.backend.services.api_gateway.schemas import (
    CaseCountResponse, BenchmarksResponse, EvaluationRequest,
    EvaluationJobResponse, JobStatusResponse, JobResultsResponse, ProgressInfo,
    ResultSummary, DetailedResult, BenchmarkInfo
)
from jarvismd.backend.services.api_gateway.settings import settings

# Define get_db function locally to avoid circular import
def get_db():
    """Dependency function to get database session for API endpoints."""
    db = get_session()
    try:
        yield db
    finally:
        db.close()

# Import paths using proper package import
from jarvismd.backend.services.api_gateway.paths import MEDICAL_CASES_DIR, PROMPTS_DIR, ensure_directories
from jarvismd.backend.services.api_gateway.prompt_parser import get_parser

logger = logging.getLogger(__name__)

# Import Celery app and tasks for background processing
try:
    # Import the configured Celery app first
    from jarvismd.backend.automation.task_queue.celery_app import celery_app
    # Then import tasks which are bound to this app
    from jarvismd.backend.automation.task_queue.tasks.evaluation_tasks import run_batch_evaluation
    from celery.result import AsyncResult  # type: ignore # noqa
    CELERY_AVAILABLE = True
    logger.info("✅ Celery tasks imported successfully")
    logger.info(f"✅ Celery broker: {celery_app.conf.broker_url}")
except ImportError as e:
    logger.warning(f"⚠️ Celery not available: {e}")
    CELERY_AVAILABLE = False
    celery_app = None
    run_batch_evaluation = None
    AsyncResult = None

router = APIRouter()

# Prometheus scrape targets for aggregating metrics (will be initialized from settings)
def get_prometheus_scrape_targets():
    """Get Prometheus scrape targets from settings"""
    from jarvismd.backend.services.api_gateway.settings import settings
    return [
        ("api", settings.get_api_metrics_url()),
        ("worker", settings.get_worker_metrics_url()),
    ]

PROMETHEUS_SCRAPE_TARGETS = get_prometheus_scrape_targets()

# ===================== REQUEST/RESPONSE MODELS =====================
def _parse_prometheus_text(text: str, source: str):
    """Parse a Prometheus metrics payload into structured entries."""
    parsed_entries = []
    for line in text.strip().split("\n"):
        if not line or line.startswith("#"):
            continue
        if " " not in line:
            continue
        metric_part, value_part = line.rsplit(" ", 1)
        try:
            value = float(value_part)
        except ValueError:
            continue
        metric_name = metric_part.split("{")[0].split(" ")[0]
        parsed_entries.append(
            {
                "metric": metric_name,
                "value": value,
                "labels": metric_part,
                "line": line,
                "source": source,
            }
        )
    return parsed_entries


def _scrape_prometheus_targets():
    """Fetch metrics text from configured Prometheus scrape targets."""
    raw_results: Dict[str, Any] = {}
    aggregated: Dict[str, List[Dict[str, Any]]] = {}

    for source, url in PROMETHEUS_SCRAPE_TARGETS:
        try:
            response = requests.get(url, timeout=3)
            response.raise_for_status()
            text = response.text
            raw_results[source] = text
            for entry in _parse_prometheus_text(text, source):
                metric_name = entry.pop("metric")
                aggregated.setdefault(metric_name, []).append(entry)
        except Exception as exc:
            logger.warning("⚠️ Failed to scrape metrics from %s (%s): %s", source, url, exc)
            raw_results[source] = {"error": str(exc)}

    combined_totals = {
        metric: sum(entry["value"] for entry in entries)
        for metric, entries in aggregated.items()
    }

    return raw_results, aggregated, combined_totals


def _calculate_p95(values: List[float]) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    index = max(0, min(len(sorted_vals) - 1, math.ceil(0.95 * len(sorted_vals)) - 1))
    return sorted_vals[index]


class SingleEvaluationRequest(BaseModel):
    """Request model for single case evaluation"""
    summary: str
    recommendation: str

class SingleEvaluationResponse(BaseModel):
    """Response model for single case evaluation"""
    success: bool
    result: Dict[str, Any]
    timestamp: str

class BatchEvaluationRequest(BaseModel):
    """Request model for batch evaluation"""
    cases: List[Dict[str, str]]  # List of {summary, recommendation, case_id}
    max_cases: int = 100  # Limit for safety

class BatchEvaluationResponse(BaseModel):
    """Response model for batch evaluation"""
    success: bool
    results: List[Dict[str, Any]]
    total_cases: int
    successful_cases: int
    failed_cases: int
    timestamp: str

class UsageMetricsResponse(BaseModel):
    """Response model for usage metrics"""
    metrics: Dict[str, Any]
    timestamp: str

# ===================== API ENDPOINTS =====================

@router.post("/evaluate/single", response_model=SingleEvaluationResponse)
async def evaluate_single_case(request: SingleEvaluationRequest):
    """
    Evaluate a single medical case using the optimized engine
    
    This endpoint uses the cached LLM instance and prompt template
    for maximum cost efficiency.
    """
    try:
        logger.info("🔍 Single case evaluation requested")
        
        # Determine prompt file path from benchmark if provided in request
        prompt_path = None
        if hasattr(request, 'benchmark_name') and request.benchmark_name:
            prompt_file = PROMPTS_DIR / f"{request.benchmark_name}.txt"
            if prompt_file.exists():
                prompt_path = prompt_file
                logger.info(f"📄 Using prompt file: {prompt_file.name}")
        
        # Evaluate using optimized engine
        result = evaluation_engine.evaluate_single_case(
            request.summary, 
            request.recommendation,
            prompt_path=prompt_path
        )
        
        return SingleEvaluationResponse(
            success=True,
            result=result,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ Single evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")

@router.post("/evaluate/batch", response_model=BatchEvaluationResponse)
async def evaluate_batch_cases(request: BatchEvaluationRequest):
    """
    Evaluate multiple medical cases efficiently
    
    Uses the optimized engine with shared LLM instance for cost efficiency.
    Limited to max_cases for safety.
    """
    try:
        if len(request.cases) > request.max_cases:
            raise HTTPException(
                status_code=400, 
                detail=f"Too many cases. Maximum allowed: {request.max_cases}"
            )
        
        logger.info(f"🔍 Batch evaluation requested: {len(request.cases)} cases")
        
        # Determine prompt file path from benchmark if provided in request
        prompt_path = None
        if hasattr(request, 'benchmark_name') and request.benchmark_name:
            prompt_file = PROMPTS_DIR / f"{request.benchmark_name}.txt"
            if prompt_file.exists():
                prompt_path = prompt_file
                logger.info(f"📄 Using prompt file: {prompt_file.name}")
        
        # Evaluate using optimized engine
        results = evaluation_engine.evaluate_batch(request.cases, prompt_path=prompt_path)
        
        # Calculate success/failure counts
        successful_cases = sum(1 for r in results if r.get('success', False))
        failed_cases = len(results) - successful_cases
        
        return BatchEvaluationResponse(
            success=True,
            results=results,
            total_cases=len(request.cases),
            successful_cases=successful_cases,
            failed_cases=failed_cases,
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Batch evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch evaluation failed: {str(e)}")

@router.post("/test/start", response_model=EvaluationJobResponse)
async def start_evaluation_test(
    request: EvaluationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start a background evaluation test using the optimized engine
    
    This is the main endpoint for running large-scale evaluations.
    Uses the cost-efficient evaluation engine.
    """
    try:
        # Automatically determine prompt file from benchmark name
        prompt_file = PROMPTS_DIR / f"{request.benchmark_name}.txt"
        
        # Validate that prompt file exists
        if not prompt_file.exists():
            available_prompts = [p.stem for p in PROMPTS_DIR.glob("*.txt")]
            raise HTTPException(
                status_code=400, 
                detail=f"Prompt file '{request.benchmark_name}.txt' not found. Available benchmarks: {available_prompts}"
            )
        
        # Get model from settings
        model_name = settings.default_model
        
        logger.info(f"🚀 Starting evaluation test: {request.num_cases} cases for benchmark: {request.benchmark_name}, model: {model_name}")
        logger.info(f"📄 Using prompt file: {prompt_file.name}")
        
        # Create test job record
        test_job = TestJob(
            total_cases=request.num_cases,
            benchmark=request.benchmark_name,
            model=model_name,
            status="running",
            start_time=datetime.now()
        )
        db.add(test_job)
        db.commit()
        db.refresh(test_job)
        
        # Start evaluation task (Celery or BackgroundTasks)
        # Revert to the previously working path by default (BackgroundTasks).
        # Only use Celery batch if explicitly enabled via USE_CELERY_BATCH=true.
        if CELERY_AVAILABLE and run_batch_evaluation and os.getenv("USE_CELERY_BATCH", "false").lower() == "true":
            try:
                # Prepare case list for Celery task
                case_list = []
                
                # Load cases from doctor folders (proper structure)
                all_case_dirs = []
                for doctor_dir in MEDICAL_CASES_DIR.iterdir():
                    if doctor_dir.is_dir() and doctor_dir.name != '__pycache__':
                        for case_dir in doctor_dir.iterdir():
                            if case_dir.is_dir():
                                all_case_dirs.append(case_dir)
                
                # Limit to requested number of cases
                case_dirs = all_case_dirs[:request.num_cases]
                logger.info(f"📂 Found {len(all_case_dirs)} total cases, loading {len(case_dirs)} cases")
                
                for case_dir in case_dirs:
                    # Extract doctor name from parent directory (dynamic, not hardcoded)
                    doctor_name = case_dir.parent.name if case_dir.parent else 'unknown'
                    
                    case_data = {
                        'case_id': case_dir.name,
                        'doctor_name': doctor_name,  # Extract from directory structure
                        'transcription': '',
                        'summary': '',
                        'recommendation': ''
                    }
                    
                    # Load case files
                    transcription_file = case_dir / "annotated_transcription.txt"
                    summary_file = case_dir / "summary.txt"
                    recommendation_file = case_dir / "recommendation.txt"
                    
                    if transcription_file.exists():
                        case_data['transcription'] = transcription_file.read_text(encoding='utf-8')
                    if summary_file.exists():
                        case_data['summary'] = summary_file.read_text(encoding='utf-8')
                    if recommendation_file.exists():
                        case_data['recommendation'] = recommendation_file.read_text(encoding='utf-8')
                    
                    # Log what was loaded for debugging
                    logger.info(f"📄 Loaded case {case_dir.name} (doctor: {doctor_name}): summary={len(case_data.get('summary', ''))} chars, recommendation={len(case_data.get('recommendation', ''))} chars")
                    case_list.append(case_data)
                
                # Start Celery task
                task = run_batch_evaluation.delay(test_job.id, case_list)
                logger.info(f"🚀 Started Celery task {task.id} for job {test_job.id}")
                test_job.celery_task_id = task.id
                test_job.status = "running"
                db.commit()
                
            except Exception as e:
                logger.error(f"❌ Failed to start Celery task: {e}")
                # Fallback to original background task if Celery fails
                background_tasks.add_task(
                    run_evaluation_job,
                    test_job.id,
                    request.num_cases,
                    request.benchmark_name
                )
        else:
            # Use original BackgroundTasks approach
            logger.info("🔄 Using BackgroundTasks (Celery not available)")
            test_job.status = "running"
            db.commit()
            background_tasks.add_task(
                run_evaluation_job,
                test_job.id,
                request.num_cases,
                request.benchmark_name
            )
        
        return EvaluationJobResponse(
            job_id=test_job.id,
            status="started",
            total_cases=request.num_cases,
            benchmark=request.benchmark_name,
            model=model_name,
            start_time=test_job.start_time.isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start evaluation test: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start test: {str(e)}")

@router.get("/metrics/usage", response_model=UsageMetricsResponse)
async def get_usage_metrics():
    """
    Get current usage metrics
    
    Shows total API calls and usage statistics.
    """
    try:
        metrics = get_evaluation_metrics()
        
        return UsageMetricsResponse(
            metrics=metrics,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@router.post("/metrics/reset")
async def reset_usage_metrics():
    """
    Reset usage metrics (useful for testing)
    
    WARNING: This will reset all usage tracking data.
    """
    try:
        reset_evaluation_metrics()
        
        return {
            "success": True,
            "message": "Usage metrics reset successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to reset metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset metrics: {str(e)}")

@router.get("/health")
async def evaluation_health():
    """
    Check the health of the evaluation engine
    
    Returns status of LLM, prompt template, and other components.
    """
    try:
        health_info = evaluation_engine.health_check()
        return health_info
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

# ===================== UTILITY FUNCTIONS =====================

async def run_evaluation_job(job_id: str, case_count: int, benchmark_type: str):
    """
    Background task to run evaluation job using optimized engine
    
    Args:
        job_id: Database job ID
        case_count: Number of cases to evaluate
        benchmark_type: Type of benchmark to run
    """
    try:
        logger.info(f"🔄 Starting background job {job_id} for {case_count} cases")
        
        # Get database session
        db = get_session()
        
        try:
            # Load medical cases
            cases = load_medical_cases(case_count)
            
            if not cases:
                raise Exception("No medical cases found")
            
            # Determine prompt file path from benchmark name
            prompt_path = None
            if benchmark_type:
                prompt_file = PROMPTS_DIR / f"{benchmark_type}.txt"
                if prompt_file.exists():
                    prompt_path = prompt_file
                    logger.info(f"📄 Using prompt file: {prompt_file.name}")
                else:
                    logger.warning(f"⚠️ Prompt file not found: {prompt_file}, will fail if no default")
            
            # Run evaluation using optimized engine
            results = evaluation_engine.evaluate_batch(cases, prompt_path=prompt_path)
            
            # Save results to database
            for i, result in enumerate(results):
                # Use model name from API response if available, otherwise fallback to settings default
                model_used = result.get('model_used') or settings.default_model
                # Extract trace_id from result if available
                trace_id = result.get('trace_id')
                eval_result = EvaluationResult(
                    test_job_id=job_id,
                    case_id=cases[i].get('case_id', f'case_{i}'),
                    doctor_name=cases[i].get('doctor_name', 'unknown'),  # Dynamic from case_data, not hardcoded
                    case_name=cases[i].get('case_id', f'case_{i}'),
                    total_score=result.get('overall_score', 0.0),
                    criteria_scores=result.get('scores', {}),
                    model_used=model_used,
                    evaluation_text=result.get('feedback', ''),
                    processing_time=result.get('processing_time', 0.0),
                    complexity_level=result.get('complexity_level', 'Unknown'),
                    trace_id=trace_id  # Store OpenTelemetry trace ID
                )
                db.add(eval_result)
            
            # Update job status
            job = db.query(TestJob).filter(TestJob.id == job_id).first()
            if job:
                job.status = "completed"
                job.end_time = datetime.now()
                job.processed_cases = len(results)
            
                db.commit()
            logger.info(f"✅ Job {job_id} completed successfully")
            
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"❌ Background job {job_id} failed: {e}")
        
        # Update job status to failed
        try:
            db = get_session()
            job = db.query(TestJob).filter(TestJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.end_time = datetime.now()
            db.commit()
        except:
            pass
    finally:
        db.close()

def load_medical_cases(count: int) -> List[Dict[str, str]]:
    """
    Load medical cases from the data directory
    
    Args:
        count: Number of cases to load
        
    Returns:
        List of case dictionaries
    """
    cases = []
    
    try:
        if not MEDICAL_CASES_DIR.exists():
            logger.warning(f"Medical cases directory not found: {MEDICAL_CASES_DIR}")
            return cases
        
        # Look inside doctor folders for actual case folders
        case_dirs = []
        for doctor_dir in MEDICAL_CASES_DIR.iterdir():
            if doctor_dir.is_dir():
                for case_dir in doctor_dir.iterdir():
                    if case_dir.is_dir():
                        case_dirs.append(case_dir)
        
        # Limit to requested count
        case_dirs = case_dirs[:count]
        
        for case_dir in case_dirs:
            try:
                # Extract doctor name from parent directory (dynamic, not hardcoded)
                doctor_name = case_dir.parent.name if case_dir.parent else 'unknown'
                
                # Load case files
                summary_file = case_dir / "summary.txt"
                recommendation_file = case_dir / "recommendation.txt"
                
                if summary_file.exists() and recommendation_file.exists():
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary = f.read().strip()
                    
                    with open(recommendation_file, 'r', encoding='utf-8') as f:
                        recommendation = f.read().strip()
                    
                    cases.append({
                        'case_id': case_dir.name,
                        'doctor_name': doctor_name,  # Extract from directory structure
                        'summary': summary,
                        'recommendation': recommendation
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to load case {case_dir.name}: {e}")
                continue
        
        logger.info(f"✅ Loaded {len(cases)} medical cases")
        
    except Exception as e:
        logger.error(f"❌ Failed to load medical cases: {e}")
    
    return cases

# ===================== LEGACY COMPATIBILITY =====================

@router.get("/cases/count", response_model=CaseCountResponse)
async def get_case_count():
    """Get total number of medical cases available (legacy endpoint)"""
    try:
        case_count = 0
        doctors = {}
        
        if MEDICAL_CASES_DIR.exists():
            # Look inside doctor folders for actual case folders
            for doctor_dir in MEDICAL_CASES_DIR.iterdir():
                if doctor_dir.is_dir():
                    doctor_name = doctor_dir.name
                    doctor_case_count = 0
                    
                    # Count case folders inside this doctor's directory
                    for case_dir in doctor_dir.iterdir():
                        if case_dir.is_dir():
                            case_count += 1
                            doctor_case_count += 1
                    
                    if doctor_case_count > 0:
                        doctors[doctor_name] = doctor_case_count
        
        return CaseCountResponse(
            total_cases=case_count,
            doctors=doctors,
            scan_time=datetime.now().isoformat(),
            data_directory=str(MEDICAL_CASES_DIR)
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to get case count: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get case count: {str(e)}")

@router.get("/benchmarks", response_model=BenchmarksResponse)
async def get_available_benchmarks():
    """Get available evaluation benchmarks by scanning prompts directory"""
    try:
        benchmarks = []
        
        # Scan prompts directory for available prompt files
        if PROMPTS_DIR.exists():
            for prompt_file in PROMPTS_DIR.glob("*.txt"):
                benchmark_id = prompt_file.stem  # Filename without extension
                
                # Calculate criteria count dynamically from prompt parser (no hardcoded assumption)
                criteria_count = None
                try:
                    from jarvismd.backend.services.api_gateway.prompt_parser import get_parser
                    parser = get_parser(prompt_file)
                    criteria_schema = parser.get_criteria_schema()
                    if criteria_schema:
                        criteria_count = len(criteria_schema)
                        logger.debug(f"✅ Calculated criteria_count for {benchmark_id}: {criteria_count}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not calculate criteria_count for {benchmark_id}: {e}")
                    # Use None if calculation fails (will be handled by frontend)
                
                benchmarks.append(BenchmarkInfo(
                    id=benchmark_id,
                    name=f"{benchmark_id.replace('_', ' ').title()} Evaluation",
                    description=f"Evaluation benchmark using {prompt_file.name}",
                    criteria_count=criteria_count,  # Dynamic count from prompt parser
                    version="1.0",
                    prompt_file=prompt_file.name
                ))
        
        # If no prompts found, return empty list
        if not benchmarks:
            logger.warning(f"No prompt files found in {PROMPTS_DIR}")
        
        return BenchmarksResponse(benchmarks=benchmarks)
        
    except Exception as e:
        logger.error(f"❌ Failed to get benchmarks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get benchmarks: {str(e)}")

@router.get("/test/{job_id}/status", response_model=JobStatusResponse)
async def get_test_status(job_id: str, db: Session = Depends(get_db)):
    """Get status of a running test job (legacy endpoint)"""
    try:
        test_job = db.query(TestJob).filter(TestJob.id == job_id).first()
        
        if not test_job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Calculate progress percentage
        processed = test_job.processed_cases or 0
        total = test_job.total_cases
        percentage = (processed / total * 100) if total > 0 else 0.0
        
        # Check Celery task status if job is running and Celery is available
        celery_status = None
        if test_job.status == 'running' and CELERY_AVAILABLE:
            try:
                # Get active tasks from Celery
                from celery import current_app  # type: ignore # noqa
                inspect = current_app.control.inspect()
                active_tasks = inspect.active()
                
                if active_tasks:
                    for worker, tasks in active_tasks.items():
                        for task in tasks:
                            if task.get('name') == 'evaluation_tasks.run_batch_evaluation':
                                task_kwargs = task.get('kwargs', {})
                                if task_kwargs.get('job_id') == job_id:
                                    celery_status = {
                                        'task_id': task.get('id'),
                                        'worker': worker,
                                        'status': 'running'
                                    }
                                    break
                        if celery_status:
                            break
                            
            except Exception as e:
                logger.warning(f"Could not check Celery task status: {e}")
                celery_status = {'error': str(e)}
        
        # Log Celery status for debugging
        if celery_status:
            logger.info(f"📊 Celery status for job {job_id}: {celery_status}")
        
        return JobStatusResponse(
            job_id=job_id,
            status=test_job.status,
            progress=ProgressInfo(
                processed=processed,
                total=total,
                percentage=round(percentage, 2)
            ),
            benchmark=test_job.benchmark,
            model=test_job.model,
            start_time=test_job.start_time.isoformat() if test_job.start_time else "",
            end_time=test_job.end_time.isoformat() if test_job.end_time else None,
            error_message=test_job.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")

@router.get("/test/{job_id}/results", response_model=JobResultsResponse)
async def get_test_results(job_id: str, db: Session = Depends(get_db)):
    """Get results from a completed test job (legacy endpoint)"""
    try:
        test_job = db.query(TestJob).filter(TestJob.id == job_id).first()
        
        if not test_job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if test_job.status != "completed":
            raise HTTPException(status_code=400, detail="Job not completed yet")
        
        # Get evaluation results
        results = db.query(EvaluationResult).filter(EvaluationResult.test_job_id == job_id).all()
        
        # Calculate summary statistics
        total_scores = [r.total_score for r in results if r.total_score is not None]
        avg_score = sum(total_scores) / len(total_scores) if total_scores else 0
        flagged_cases = len([r for r in results if r.total_score < 75.0])
        
        # Get criteria schema from prompt parser using the benchmark's prompt file
        try:
            prompt_path = PROMPTS_DIR / f"{test_job.benchmark}.txt" if test_job.benchmark else None
            if prompt_path and prompt_path.exists():
                parser = get_parser(prompt_path)
                criteria_schema = parser.get_criteria_schema()
                criterion_max_scores = parser.get_max_scores_map()  # Keep for backward compatibility
                criterion_name_to_max_score = parser.get_criterion_name_to_max_score_map()  # Keep for backward compatibility
                logger.info(f"✅ Loaded criteria schema: {len(criteria_schema) if criteria_schema else 0} criteria from {prompt_path.name}")
            else:
                logger.warning(f"⚠️ Prompt file not found for benchmark {test_job.benchmark}, criteria schema unavailable")
                criteria_schema = None
                criterion_max_scores = None
                criterion_name_to_max_score = None
        except Exception as e:
            logger.error(f"❌ Failed to load criteria schema: {e}", exc_info=True)
            criteria_schema = None
            criterion_max_scores = None
            criterion_name_to_max_score = None
        
        return JobResultsResponse(
            job_id=job_id,
            summary=ResultSummary(
                total_evaluations=len(results),
                average_score=round(avg_score, 2),
                benchmark=test_job.benchmark,
                model=test_job.model,
                completion_time=test_job.end_time.isoformat() if test_job.end_time else None,
                cases_flagged_for_review=flagged_cases,
                review_threshold=75.0
            ),
            detailed_results=[
                DetailedResult(
                    case_id=result.case_id,
                    doctor_name=result.doctor_name,
                    case_name=result.case_name,
                    total_score=result.total_score,
                    criteria_scores=result.criteria_scores,
                    processing_time=result.processing_time,
                    created_at=result.created_at.isoformat(),
                    complexity_level=result.complexity_level,
                    flagged_for_review=result.total_score < 75.0,
                    review_priority="high" if result.total_score < 50.0 else ("medium" if result.total_score < 75.0 else "none"),
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    total_tokens=result.total_tokens,
                    evaluation_text=result.evaluation_text,
                    trace_id=result.trace_id,  # Include OpenTelemetry trace ID
                ) for result in results
            ],
            criteria_schema=criteria_schema,
            criterion_max_scores=criterion_max_scores,  # Deprecated, use criteria_schema
            criterion_name_to_max_score=criterion_name_to_max_score  # Deprecated, use criteria_schema
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get job results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job results: {str(e)}")

# ===================== METRICS ENDPOINTS =====================

@router.post("/test/{job_id}/cancel")
async def cancel_test_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a running evaluation job."""
    test_job = db.query(TestJob).filter(TestJob.id == job_id).first()

    if not test_job:
        raise HTTPException(status_code=404, detail="Job not found")

    if test_job.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="Job is not running and cannot be cancelled")

    if not CELERY_AVAILABLE or not celery_app:
        raise HTTPException(status_code=503, detail="Cancellation requires Celery to be enabled")

    if not test_job.celery_task_id:
        raise HTTPException(status_code=409, detail="No Celery task associated with this job")

    try:
        celery_app.control.revoke(test_job.celery_task_id, terminate=True, signal="SIGTERM")
    except Exception as exc:
        logger.warning(f"⚠️ Failed to revoke Celery task {test_job.celery_task_id}: {exc}")

    test_job.status = "cancelled"
    test_job.end_time = datetime.now()
    db.commit()

    return {
        "success": True,
        "job_id": job_id,
        "status": test_job.status,
    }

def _get_target_job(db: Session, job_id: Optional[str] = None) -> Optional[TestJob]:
    if job_id:
        return db.query(TestJob).filter(TestJob.id == job_id).first()
    return (
        db.query(TestJob)
        .filter(TestJob.status == "completed")
        .order_by(TestJob.end_time.desc(), TestJob.start_time.desc())
        .first()
    )


def _serialize_case(result: EvaluationResult, index: int) -> Dict[str, Any]:
    return {
        "order": index,
        "case_id": result.case_id,
        "score": result.total_score,
        "processing_time": result.processing_time,
        "flagged": (result.total_score or 0) < 75.0,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }


@router.get("/metrics/job/latest")
async def get_latest_job_metrics(
    job_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return analytics for the latest completed job (or specific job if job_id provided)."""
    try:
        job = _get_target_job(db, job_id)
        if not job:
            # Return null instead of 404 when no jobs exist - this is expected for empty state
            return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get target job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job: {str(e)}")

    try:
        results = (
            db.query(EvaluationResult)
            .filter(EvaluationResult.test_job_id == job.id)
            .order_by(EvaluationResult.created_at.asc())
            .all()
        )

        total_cases = job.total_cases or len(results)
        success_count = len(results)
        failure_count = max(total_cases - success_count, 0) if total_cases is not None else 0
        success_rate = (success_count / total_cases * 100) if total_cases else 0.0

        durations = [r.processing_time for r in results if r.processing_time is not None]
        p95_duration = _calculate_p95(durations)
        average_duration = sum(durations) / len(durations) if durations else 0.0

        flagged_cases = len([r for r in results if (r.total_score or 0) < 75.0])
        prompt_tokens = sum(r.prompt_tokens or 0 for r in results)
        completion_tokens = sum(r.completion_tokens or 0 for r in results)
        total_tokens = sum(r.total_tokens or 0 for r in results)


        cases_payload = [
            _serialize_case(result, idx + 1)
            for idx, result in enumerate(results)
        ]

        return {
            "job": {
            "id": job.id,
            "benchmark": job.benchmark,
            "model": job.model,
            "total_cases": job.total_cases,
            "processed_cases": job.processed_cases,
            "status": job.status,
            "start_time": job.start_time.isoformat() if job.start_time else None,
            "end_time": job.end_time.isoformat() if job.end_time else None,
        },
        "summary": {
            "success_rate": round(success_rate, 2),
            "success_count": success_count,
            "failure_count": failure_count,
            "flagged_cases": flagged_cases,
            "p95_duration_seconds": round(p95_duration, 2),
            "average_duration_seconds": round(average_duration, 2),
            "cases_processed": success_count,
            "total_cases": total_cases,
        },
        "tokens": {
            "input": prompt_tokens,
            "output": completion_tokens,
            "total": total_tokens,
        },
        "durations": {
            "count": len(durations),
            "min": min(durations) if durations else 0.0,
            "max": max(durations) if durations else 0.0,
            "sum": sum(durations) if durations else 0.0,
        },
        "cases": cases_payload,
        }
    except Exception as e:
        logger.error(f"❌ Failed to get latest job metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job metrics: {str(e)}")


@router.get("/metrics")
async def get_metrics():
    """Get comprehensive evaluation metrics including Prometheus metrics."""
    try:
        # Get usage and Prometheus metrics
        usage_metrics = get_evaluation_metrics()
        raw_metrics, aggregated_metrics, combined_totals = _scrape_prometheus_targets()

        prometheus_metrics = {
            "parsed_metrics": aggregated_metrics,
            "raw_metrics": raw_metrics,
            "combined_totals": combined_totals,
            "sources": {source: url for source, url in PROMETHEUS_SCRAPE_TARGETS},
        }

        # Fallback: include local metrics if scraping failed completely
        if not aggregated_metrics:
            try:
                fallback = get_prometheus_metrics()
                prometheus_metrics.setdefault("fallback", fallback)
            except Exception as fallback_error:
                logger.warning("⚠️ Fallback Prometheus metrics unavailable: %s", fallback_error)

        # Get metrics URL from settings
        from jarvismd.backend.services.api_gateway.settings import settings
        metrics_url = settings.get_api_metrics_url()

        return {
            "timestamp": datetime.now().isoformat(),
            "usage_metrics": usage_metrics,
            "prometheus_metrics": prometheus_metrics,
            "metrics_endpoint": metrics_url
        }
    except Exception as e:
        logger.error(f"❌ Failed to get metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@router.get("/metrics/prometheus")
async def get_prometheus_metrics_endpoint():
    """Get Prometheus-formatted metrics."""
    try:
        return get_prometheus_metrics()
    except Exception as e:
        logger.error(f"❌ Failed to get Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Prometheus metrics: {str(e)}")

@router.post("/metrics/reset")
async def reset_metrics():
    """Reset all evaluation metrics."""
    try:
        reset_evaluation_metrics()
        return {
            "message": "Metrics reset successfully",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Failed to reset metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset metrics: {str(e)}")
    