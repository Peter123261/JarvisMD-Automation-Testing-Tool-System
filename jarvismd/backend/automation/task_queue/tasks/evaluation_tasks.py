"""
Celery Tasks for Medical Case Evaluation
Handles individual case evaluation and batch processing
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from celery import current_task  # type: ignore
from celery.exceptions import Retry  # type: ignore

# Import Celery app - will be set by celery_app.py to avoid circular import
from celery import current_app  # type: ignore

# Import database components using proper package imports
from jarvismd.backend.database.database import get_session
from jarvismd.backend.database.models import TestJob, EvaluationResult
from sqlalchemy import inspect, text

# Don't import EvaluationEngine at module level to avoid loading settings
# It will be imported inside functions when actually needed
# Import settings for model configuration (lazy import pattern)
def _get_default_model():
    """Get default model from settings (lazy import to avoid loading settings at module level)"""
    from jarvismd.backend.services.api_gateway.settings import settings
    return settings.default_model

# Centralized error logging
try:
    from jarvismd.backend.shared.utils.error_logger import log_full_error
except ImportError:
    # Fallback if import fails
    import traceback
    def log_full_error(error: Exception, context: dict = None, log_level: str = "error"):
        """Fallback error logger if import fails"""
        logger.error(f"Error: {type(error).__name__}: {str(error)}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")

# OpenTelemetry Celery instrumentation (lazy import to avoid loading at module level)
def _setup_celery_instrumentation():
    """Setup Celery instrumentation for OpenTelemetry"""
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor  # type: ignore
        CeleryInstrumentor().instrument()
        logger.info("✅ Celery OpenTelemetry instrumentation initialized")
    except Exception as e:
        logger.warning(f"⚠️ Celery OpenTelemetry instrumentation failed: {e}")

logger = logging.getLogger(__name__)

# Initialize Celery instrumentation on module load
_setup_celery_instrumentation()


def get_trace_id() -> str | None:
    """
    Returns the current span's trace_id or None if not active.
    This is a defensive helper to ensure trace_id is always available.
    """
    try:
        from opentelemetry import trace  # type: ignore
        span = trace.get_current_span()
        if span:
            span_context = span.get_span_context()
            if span_context and span_context.is_valid:
                return format(span_context.trace_id, '032x')
    except Exception:
        pass  # Silently return None if extraction fails
    return None

_token_columns_checked = False

def _ensure_token_columns(session):
    """
    Ensure token columns exist on evaluation_results table (for legacy databases).
    """
    global _token_columns_checked
    if _token_columns_checked:
        return

    bind = session.get_bind()
    inspector = inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('evaluation_results')}

    alter_statements = []
    if 'prompt_tokens' not in existing_columns:
        alter_statements.append('ALTER TABLE evaluation_results ADD COLUMN prompt_tokens INTEGER')
    if 'completion_tokens' not in existing_columns:
        alter_statements.append('ALTER TABLE evaluation_results ADD COLUMN completion_tokens INTEGER')
    if 'total_tokens' not in existing_columns:
        alter_statements.append('ALTER TABLE evaluation_results ADD COLUMN total_tokens INTEGER')

    for statement in alter_statements:
        try:
            bind.execute(text(statement))
        except Exception as exc:
            logger.warning(f"⚠️ Unable to alter evaluation_results table: {exc}")

    _token_columns_checked = True


def _evaluate_case_sync(case_data: Dict[str, Any], job_id: str, prompt_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Synchronous case evaluation (called from batch task, not as a separate Celery task)
    
    Args:
        case_data: Dictionary containing case information
        job_id: ID of the parent evaluation job
        prompt_path: Optional path to prompt file to use for evaluation
        
    Returns:
        Dictionary with evaluation results
    """
    try:
        logger.info(f"🔍 Starting evaluation for case: {case_data.get('case_id', 'unknown')}")
        
        # Initialize evaluation engine (lazy import to avoid loading settings at module level)
        from jarvismd.backend.services.api_gateway.evaluation_engine import EvaluationEngine
        from pathlib import Path
        import time
        
        engine = EvaluationEngine(prompt_path=prompt_path)
        
        # RETRY LOGIC: Attempt evaluation with 1 retry on failure
        max_attempts = 2  # 1 initial attempt + 1 retry
        result = None
        processing_time = 0
        failed_trace_id = None  # Store trace_id from failed attempts
        
        for attempt in range(1, max_attempts + 1):
            # Run evaluation
            start_time = datetime.now()
            result = engine.evaluate_single_case(
                summary=case_data.get('summary', ''),
                recommendation=case_data.get('recommendation', ''),
                prompt_path=prompt_path
            )
            end_time = datetime.now()
            
            # Calculate processing time for this attempt
            attempt_time = (end_time - start_time).total_seconds()
            processing_time += attempt_time
            
            # Check if evaluation succeeded
            eval_success = result.get('success', True)
            error_type = result.get('error_type', 'unknown')
            
            # Extract trace_id from result early (before span context might be lost)
            result_trace_id = result.get('trace_id') if isinstance(result, dict) else None
            if result_trace_id:
                failed_trace_id = result_trace_id  # Store for use if all attempts fail
            
            # ALWAYS try to get trace_id from span if we don't have one yet
            # This ensures we capture it even if the result doesn't include it
            if not failed_trace_id:
                span_trace_id = get_trace_id()
                if span_trace_id:
                    failed_trace_id = span_trace_id
            
            if eval_success:
                # Success! No need to retry
                if attempt > 1:
                    logger.info(f"✅ Case {case_data.get('case_id')} succeeded on retry attempt {attempt}")
                break
            else:
                # Failed - check if we should retry
                logger.warning(f"⚠️ Attempt {attempt}/{max_attempts} failed for case {case_data.get('case_id')}")
                logger.warning(f"🚨 Error Type: {error_type}")
                
                if attempt < max_attempts:
                    # Retry with a short delay
                    retry_delay = 3  # 3 seconds between attempts
                    logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    processing_time += retry_delay
                else:
                    # Final attempt failed - log detailed error
                    logger.error(f"❌ Case {case_data.get('case_id')} PERMANENTLY FAILED after {max_attempts} attempts!")
                    logger.error(f"🚨 Final Error Type: {error_type}")
                    logger.error(f"📄 Error Details: {result.get('feedback', 'No details')}")
                    logger.error(f"⏱️ Total time (including retries): {processing_time:.2f}s")
                    
                    # Extract trace_id from result if available (for failed cases)
                    # Use the trace_id we captured from failed attempts, or try to get it from current result/span
                    trace_id = failed_trace_id if failed_trace_id else (result.get('trace_id') if isinstance(result, dict) else None)
                    
                    # Defensive: Always ensure trace_id is set, even if extraction above failed
                    if not trace_id:
                        trace_id = get_trace_id()
                    
                    if not trace_id:
                        logger.warning(f"⚠️ No trace_id found for failed case {case_data.get('case_id')}")
                    
                    # Always include trace_id in the result, even if None
                    failed_result = {
                        'success': False,
                        'case_id': case_data.get('case_id'),
                        'overall_score': 0.0,
                        'complexity_level': 'Unknown',
                        'processing_time': processing_time,
                        'error': error_type,
                        'error_details': result.get('feedback', '')[:500],
                        'retry_attempts': max_attempts,
                        'trace_id': trace_id  # Include trace_id for failed cases
                    }
                    
                    # Defensive: Ensure trace_id is set one more time before returning
                    if not failed_result.get('trace_id'):
                        failed_result['trace_id'] = get_trace_id()
                    
                    return failed_result
        
        # Evaluation succeeded - save to database
        with get_session() as db:
            _ensure_token_columns(db)

            token_usage = result.get('token_usage', {}) or {}
            # Debug: Log the exact scores structure we are about to persist
            try:
                logger.info("🧪 Persisting criteria scores (run_single_case_sync):")
                logger.info(result.get('scores', {}))
            except Exception as _log_err:
                logger.warning(f"⚠️ Failed to log scores prior to DB save (sync): {_log_err}")
            # Create evaluation result record
            # Use model name from API response if available, otherwise fallback to default
            model_used = result.get('model_used') or _get_default_model()
            # Extract trace_id from result if available
            trace_id = result.get('trace_id')
            if trace_id:
                logger.info(f"📊 Extracted trace_id from result: {trace_id}")
            else:
                logger.warning(f"⚠️ No trace_id found in evaluation result for case {case_data.get('case_id')}")
            eval_result = EvaluationResult(
                test_job_id=job_id,
                case_id=case_data.get('case_id'),
                doctor_name=case_data.get('doctor_name', 'unknown'),  # Dynamic from case_data, not hardcoded
                case_name=case_data.get('case_id'),
                total_score=result.get('overall_score', 0.0),
                criteria_scores=result.get('scores', {}),
                model_used=model_used,
                evaluation_text=result.get('feedback', ''),
                processing_time=processing_time,
                complexity_level=result.get('complexity_level', 'Unknown'),
                prompt_tokens=token_usage.get('prompt_tokens'),
                completion_tokens=token_usage.get('completion_tokens'),
                total_tokens=token_usage.get('total_tokens'),
                trace_id=trace_id  # Store OpenTelemetry trace ID
            )
            
            db.add(eval_result)
            db.commit()
            
            logger.info(f"✅ Case {case_data.get('case_id')} evaluated successfully")
            logger.info(f"📊 Score: {result.get('overall_score', 0.0)}")
            
            return {
                'success': True,
                'case_id': case_data.get('case_id'),
                'overall_score': result.get('overall_score', 0.0),
                'complexity_level': result.get('complexity_level', 'Unknown'),
                'processing_time': processing_time
            }
            
    except Exception as e:
        log_full_error(
            e,
            context={
                'function': '_evaluate_case_sync',
                'job_id': job_id,
                'case_id': case_data.get('case_id')
            }
        )
        
        # Always extract trace_id from current span for exception case
        exception_trace_id = get_trace_id()
        
        exception_result = {
            'success': False,
            'case_id': case_data.get('case_id'),
            'error': str(e),
            'trace_id': exception_trace_id  # Include trace_id even for exceptions
        }
        
        # Defensive: Ensure trace_id is set one more time before returning
        if not exception_result.get('trace_id'):
            exception_result['trace_id'] = get_trace_id()
        
        return exception_result

@current_app.task(bind=True, name='evaluation_tasks.run_single_case_evaluation')
def run_single_case_evaluation(self, case_data: Dict[str, Any], job_id: str, prompt_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Evaluate a single medical case using the evaluation engine
    
    Args:
        case_data: Dictionary containing case information
        job_id: ID of the parent evaluation job
        prompt_path: Optional path string to prompt file to use for evaluation
        
    Returns:
        Dictionary with evaluation results
    """
    try:
        logger.info(f"🔍 Starting evaluation for case: {case_data.get('case_id', 'unknown')}")
        
        # Update task progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 1, 'status': 'Evaluating case...'}
        )
        
        # Initialize evaluation engine (lazy import to avoid loading settings at module level)
        from jarvismd.backend.services.api_gateway.evaluation_engine import EvaluationEngine
        from jarvismd.backend.services.api_gateway.paths import PROMPTS_DIR
        
        # Convert prompt_path string to Path if provided
        prompt_path_obj = None
        if prompt_path:
            if isinstance(prompt_path, str):
                prompt_path_obj = Path(prompt_path) if Path(prompt_path).is_absolute() else PROMPTS_DIR / prompt_path
            else:
                prompt_path_obj = prompt_path
        
        engine = EvaluationEngine(prompt_path=prompt_path_obj)
        
        # Run evaluation
        start_time = datetime.now()
        result = engine.evaluate_single_case(
            summary=case_data.get('summary', ''),
            recommendation=case_data.get('recommendation', ''),
            prompt_path=prompt_path_obj
        )
        end_time = datetime.now()
        
        # Calculate processing time
        processing_time = (end_time - start_time).total_seconds()
        
        # Save result to database
        with get_session() as db:
            _ensure_token_columns(db)

            token_usage = result.get('token_usage', {}) or {}
            # Debug: Log the exact scores structure we are about to persist
            try:
                logger.info("🧪 Persisting criteria scores (run_single_case_evaluation):")
                logger.info(result.get('scores', {}))
            except Exception as _log_err:
                logger.warning(f"⚠️ Failed to log scores prior to DB save (celery): {_log_err}")
            # Create evaluation result record
            # Use model name from API response if available, otherwise fallback to default
            model_used = result.get('model_used') or _get_default_model()
            # Extract trace_id from result if available
            trace_id = result.get('trace_id')
            if trace_id:
                logger.info(f"📊 Extracted trace_id from result: {trace_id}")
            else:
                logger.warning(f"⚠️ No trace_id found in evaluation result for case {case_data.get('case_id')}")
            eval_result = EvaluationResult(
                test_job_id=job_id,
                case_id=case_data.get('case_id'),
                doctor_name=case_data.get('doctor_name', 'unknown'),  # Dynamic from case_data, not hardcoded
                case_name=case_data.get('case_id'),
                total_score=result.get('overall_score', 0.0),
                criteria_scores=result.get('scores', {}),
                model_used=model_used,
                evaluation_text=result.get('feedback', ''),
                processing_time=processing_time,
                complexity_level=result.get('complexity_level', 'Unknown'),
                prompt_tokens=token_usage.get('prompt_tokens'),
                completion_tokens=token_usage.get('completion_tokens'),
                total_tokens=token_usage.get('total_tokens'),
                trace_id=trace_id  # Store OpenTelemetry trace ID
            )
            
            db.add(eval_result)
            db.commit()
            
            logger.info(f"✅ Case {case_data.get('case_id')} evaluated successfully")
            logger.info(f"📊 Score: {result.get('overall_score', 0.0)}")
            
            return {
                'success': True,
                'case_id': case_data.get('case_id'),
                'overall_score': result.get('overall_score', 0.0),
                'scores': result.get('scores', {}),
                'feedback': result.get('feedback', ''),
                'processing_time': processing_time,
                'complexity_level': result.get('complexity_level', 'Unknown'),
                'task_id': self.request.id
            }
            
    except Exception as e:
        log_full_error(
            e,
            context={
                'function': 'run_single_case_evaluation',
                'job_id': job_id,
                'case_id': case_data.get('case_id', 'unknown'),
                'task_id': self.request.id
            }
        )
        
        # Retry logic - 1 RETRY ONLY
        try:
            raise self.retry(countdown=60, max_retries=1, exc=e)
        except Retry:
            # Max retries reached, return failure
            return {
                'success': False,
                'case_id': case_data.get('case_id'),
                'error': str(e),
                'task_id': self.request.id
            }

@current_app.task(bind=True, name='evaluation_tasks.run_batch_evaluation')
def run_batch_evaluation(self, job_id: str, case_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Process a batch of medical cases for evaluation
    
    Args:
        job_id: ID of the evaluation job
        case_list: List of case data dictionaries
        
    Returns:
        Dictionary with batch processing results
    """
    try:
        total_cases = len(case_list)
        logger.info(f"🚀 Starting batch evaluation: {total_cases} cases for job {job_id}")
        
        # Get prompt path from job benchmark
        prompt_path = None
        with get_session() as db:
            job = db.query(TestJob).filter(TestJob.id == job_id).first()
            if job:
                job.status = 'running'
                job.start_time = datetime.now()
                db.commit()
                
                # Determine prompt file path from benchmark name
                if job.benchmark:
                    from jarvismd.backend.services.api_gateway.paths import PROMPTS_DIR
                    prompt_file = PROMPTS_DIR / f"{job.benchmark}.txt"
                    if prompt_file.exists():
                        prompt_path = prompt_file
                        logger.info(f"📄 Using prompt file: {prompt_file.name}")
                    else:
                        logger.warning(f"⚠️ Prompt file not found: {prompt_file}, will use default")
                else:
                    logger.warning(f"⚠️ No benchmark specified for job {job_id}")
        
        results = []
        successful_cases = 0
        failed_cases = 0
        cancelled = False
        
        for i, case_data in enumerate(case_list, 1):
            try:
                # Check if job has been cancelled
                with get_session() as db:
                    job = db.query(TestJob).filter(TestJob.id == job_id).first()
                    if job and job.status == 'cancelled':
                        logger.info(f"🛑 Job {job_id} marked as cancelled, stopping evaluation loop.")
                        cancelled = True
                        break

                # Update progress
                progress = (i / total_cases) * 100
                current_task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i,
                        'total': total_cases,
                        'status': f'Processing case {i}/{total_cases}',
                        'progress': round(progress, 2)
                    }
                )
                
                # Evaluate single case inline (not as a Celery task)
                result = _evaluate_case_sync(case_data, job_id, prompt_path)
                
                if result.get('success'):
                    successful_cases += 1
                    results.append(result)
                    logger.info(f"✅ Case {i}/{total_cases} completed")
                    
                    # Ensure persistence for this case (defensive, avoids missing rows if upstream save failed)
                    try:
                        with get_session() as db:
                            _ensure_token_columns(db)
                            
                            # Check if a row already exists for this job+case
                            existing = db.query(EvaluationResult).filter(
                                EvaluationResult.test_job_id == job_id,
                                EvaluationResult.case_id == case_data.get('case_id')
                            ).first()
                            
                            if not existing:
                                # Persist minimal fields available from result; upstream path should have saved full details
                                token_usage = (result.get('token_usage') or {}) if isinstance(result, dict) else {}
                                try:
                                    logger.info("🧪 Persisting criteria scores (run_batch_evaluation):")
                                    logger.info(result.get('scores', {}) if isinstance(result, dict) else {})
                                except Exception as _log_err:
                                    logger.warning(f"⚠️ Failed to log scores prior to DB save (batch): {_log_err}")
                                
                                # Use model name from API response if available, otherwise fallback to default
                                model_used = (result.get('model_used') if isinstance(result, dict) else None) or _get_default_model()
                                # Extract trace_id from result if available
                                trace_id = result.get('trace_id') if isinstance(result, dict) else None
                                eval_result = EvaluationResult(
                                    test_job_id=job_id,
                                    case_id=case_data.get('case_id'),
                                    doctor_name=case_data.get('doctor_name', 'unknown'),  # Dynamic from case_data, not hardcoded
                                    case_name=case_data.get('case_id'),
                                    total_score=result.get('overall_score', 0.0) if isinstance(result, dict) else 0.0,
                                    criteria_scores=result.get('scores', {}) if isinstance(result, dict) else {},
                                    model_used=model_used,
                                    evaluation_text=result.get('feedback', '') if isinstance(result, dict) else '',
                                    processing_time=result.get('processing_time', 0.0) if isinstance(result, dict) else 0.0,
                                    complexity_level=result.get('complexity_level', 'Unknown') if isinstance(result, dict) else 'Unknown',
                                    prompt_tokens=token_usage.get('prompt_tokens'),
                                    completion_tokens=token_usage.get('completion_tokens'),
                                    total_tokens=token_usage.get('total_tokens'),
                                    trace_id=trace_id  # Store OpenTelemetry trace ID
                                )
                                db.add(eval_result)
                                db.commit()
                    except Exception as persist_err:
                        logger.warning(f"⚠️ Defensive persist in batch failed for case {case_data.get('case_id')}: {persist_err}")
                else:
                    failed_cases += 1
                    logger.error(f"❌ Case {i}/{total_cases} failed: {result.get('error')}")
                    
                    # Save failed case to database with score 0.0
                    try:
                        with get_session() as db:
                            _ensure_token_columns(db)
                            
                            # Check if a row already exists for this job+case
                            existing = db.query(EvaluationResult).filter(
                                EvaluationResult.test_job_id == job_id,
                                EvaluationResult.case_id == case_data.get('case_id')
                            ).first()
                            
                            if not existing:
                                # Extract error information
                                error_type = result.get('error_type', 'UnknownError') if isinstance(result, dict) else 'UnknownError'
                                error_message = result.get('error', result.get('error_details', 'Evaluation failed')) if isinstance(result, dict) else 'Evaluation failed'
                                error_details = f"Evaluation failed: {error_type} - {error_message}"
                                processing_time = result.get('processing_time', 0.0) if isinstance(result, dict) else 0.0
                                
                                # Extract trace_id from result if available
                                trace_id = result.get('trace_id') if isinstance(result, dict) else None
                                
                                # ALWAYS call get_trace_id() defensively - don't rely on result having it
                                # This ensures we get trace_id from the active span even if result doesn't have it
                                if not trace_id:
                                    trace_id = get_trace_id()
                                    # Try one more time if first attempt failed
                                    if not trace_id:
                                        trace_id = get_trace_id()
                                
                                # Defensive: One final check before saving - NEVER allow trace_id to be omitted
                                if not trace_id:
                                    trace_id = get_trace_id()
                                
                                # Use model name from result or default
                                model_used = (result.get('model_used') if isinstance(result, dict) else None) or _get_default_model()
                                
                                # Create evaluation result record for failed case
                                # NEVER allow trace_id to be omitted - use defensive extraction
                                eval_result = EvaluationResult(
                                    test_job_id=job_id,
                                    case_id=case_data.get('case_id'),
                                    doctor_name=case_data.get('doctor_name', 'unknown'),
                                    case_name=case_data.get('case_id'),
                                    total_score=0.0,  # Failed cases get 0.0 score
                                    criteria_scores={},  # Empty scores for failed cases
                                    model_used=model_used,
                                    evaluation_text=error_details,  # Store error details
                                    processing_time=processing_time,
                                    complexity_level='Unknown',
                                    prompt_tokens=None,
                                    completion_tokens=None,
                                    total_tokens=None,
                                    trace_id=trace_id  # Always set trace_id (may be None if span not available)
                                )
                                db.add(eval_result)
                                db.commit()
                                logger.info(f"💾 Saved failed case {case_data.get('case_id')} to database with score 0.0")
                    except Exception as persist_err:
                        logger.warning(f"⚠️ Failed to save failed case {case_data.get('case_id')} to database: {persist_err}")
                    
            except Exception as e:
                failed_cases += 1
                log_full_error(
                    e,
                    context={
                        'function': 'run_batch_evaluation',
                        'job_id': job_id,
                        'case_index': i,
                        'total_cases': total_cases,
                        'case_id': case_data.get('case_id', f'case_{i}')
                    }
                )
                
                # Save failed case to database with score 0.0 (exception case)
                try:
                    with get_session() as db:
                        _ensure_token_columns(db)
                        
                        # Check if a row already exists for this job+case
                        existing = db.query(EvaluationResult).filter(
                            EvaluationResult.test_job_id == job_id,
                            EvaluationResult.case_id == case_data.get('case_id')
                        ).first()
                        
                        if not existing:
                            error_details = f"Evaluation failed with exception: {type(e).__name__} - {str(e)}"
                            
                            # Use default model
                            model_used = _get_default_model()
                            
                            # Always extract trace_id from current OpenTelemetry span
                            exception_trace_id = get_trace_id()
                            
                            # Defensive: One final check before saving
                            if not exception_trace_id:
                                exception_trace_id = get_trace_id()
                            
                            # Create evaluation result record for failed case
                            # NEVER allow trace_id to be omitted
                            eval_result = EvaluationResult(
                                test_job_id=job_id,
                                case_id=case_data.get('case_id'),
                                doctor_name=case_data.get('doctor_name', 'unknown'),
                                case_name=case_data.get('case_id'),
                                total_score=0.0,  # Failed cases get 0.0 score
                                criteria_scores={},  # Empty scores for failed cases
                                model_used=model_used,
                                evaluation_text=error_details,  # Store exception details
                                processing_time=0.0,
                                complexity_level='Unknown',
                                prompt_tokens=None,
                                completion_tokens=None,
                                total_tokens=None,
                                trace_id=exception_trace_id  # Always set trace_id (may be None if span not available)
                            )
                            db.add(eval_result)
                            db.commit()
                            logger.info(f"💾 Saved failed case {case_data.get('case_id')} to database with score 0.0 (exception)")
                except Exception as persist_err:
                    logger.warning(f"⚠️ Failed to save failed case {case_data.get('case_id')} to database: {persist_err}")
                
                # Always include trace_id in exception result
                exception_result_trace_id = get_trace_id()
                results.append({
                    'success': False,
                    'case_id': case_data.get('case_id'),
                    'error': str(e),
                    'trace_id': exception_result_trace_id  # Include trace_id even for exceptions
                })
        
        # Update job completion
        with get_session() as db:
            job = db.query(TestJob).filter(TestJob.id == job_id).first()
            if job:
                if job.status != 'cancelled':
                    job.status = 'completed'
                    job.end_time = datetime.now()
                    job.processed_cases = successful_cases
                    job.total_cases = total_cases
                    db.commit()
        
        # Calculate summary statistics
        total_score = sum(r.get('overall_score', 0) for r in results if r.get('success'))
        average_score = total_score / successful_cases if successful_cases > 0 else 0
        
        if cancelled:
            logger.info(f"🛑 Batch evaluation for job {job_id} cancelled by user.")
        else:
            logger.info(f"🎉 Batch evaluation completed!")
            logger.info(f"📊 Success: {successful_cases}, Failed: {failed_cases}")
            logger.info(f"📈 Average Score: {average_score:.2f}")
        
        return {
            'success': not cancelled,
            'job_id': job_id,
            'total_cases': total_cases,
            'successful_cases': successful_cases,
            'failed_cases': failed_cases,
            'average_score': round(average_score, 2),
            'results': results,
            'status': 'cancelled' if cancelled else 'completed',
            'task_id': self.request.id
        }
        
    except Exception as e:
        log_full_error(
            e,
            context={
                'function': 'run_batch_evaluation',
                'job_id': job_id,
                'task_id': self.request.id
            }
        )
        
        # Update job status to failed
        with get_session() as db:
            job = db.query(TestJob).filter(TestJob.id == job_id).first()
            if job:
                job.status = 'failed'
                job.end_time = datetime.now()
                db.commit()
        
        return {
            'success': False,
            'job_id': job_id,
            'error': str(e),
            'task_id': self.request.id
        }

@current_app.task(name='evaluation_tasks.get_evaluation_status')
def get_evaluation_status(job_id: str) -> Dict[str, Any]:
    """
    Get the current status of an evaluation job
    
    Args:
        job_id: ID of the evaluation job
        
    Returns:
        Dictionary with job status information
    """
    try:
        with get_session() as db:
            job = db.query(TestJob).filter(TestJob.id == job_id).first()
            
            if not job:
                return {'error': f'Job {job_id} not found'}
            
            # Get results count
            results_count = db.query(EvaluationResult).filter(
                EvaluationResult.job_id == job_id
            ).count()
            
            return {
                'job_id': job_id,
                'status': job.status,
                'total_cases': job.total_cases or 0,
                'processed_cases': results_count,
                'progress_percentage': (results_count / (job.total_cases or 1)) * 100 if job.total_cases else 0,
                'start_time': job.start_time.isoformat() if job.start_time else None,
                'end_time': job.end_time.isoformat() if job.end_time else None
            }
            
    except Exception as e:
        log_full_error(e, context={'function': 'get_job_status', 'job_id': job_id})
        return {'error': str(e)}
