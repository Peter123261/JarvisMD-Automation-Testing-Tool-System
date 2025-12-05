"""
Celery Tasks for Medical Case Evaluation
Handles individual case evaluation and batch processing
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from celery import current_task
from celery.exceptions import Retry

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
sys.path.insert(0, project_root)

# Import Celery app and database components
from backend.automation.task_queue.celery_app import celery_app
from backend.database.database import get_db_session
from backend.database.models import TestJob, EvaluationResult
from backend.services.api_gateway.evaluation_engine import EvaluationEngine

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name='evaluation_tasks.run_single_case_evaluation')
def run_single_case_evaluation(self, case_data: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    """
    Evaluate a single medical case using the evaluation engine
    
    Args:
        case_data: Dictionary containing case information
        job_id: ID of the parent evaluation job
        
    Returns:
        Dictionary with evaluation results
    """
    try:
        logger.info(f"🔍 Starting evaluation for case: {case_data.get('case_id', 'unknown')}")
        
        # Update task progress
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 1, 'status': 'Evaluating case...'}
        )
        
        # Initialize evaluation engine
        engine = EvaluationEngine()
        
        # Run evaluation
        start_time = datetime.now()
        result = engine.evaluate_case(
            case_id=case_data.get('case_id'),
            transcription=case_data.get('transcription', ''),
            summary=case_data.get('summary', ''),
            recommendation=case_data.get('recommendation', '')
        )
        end_time = datetime.now()
        
        # Calculate processing time
        processing_time = (end_time - start_time).total_seconds()
        
        # Save result to database
        with get_db_session() as db:
            # Create evaluation result record
            eval_result = EvaluationResult(
                job_id=job_id,
                case_id=case_data.get('case_id'),
                overall_score=result.get('overall_score', 0.0),
                detailed_scores=result.get('scores', {}),
                feedback=result.get('feedback', ''),
                processing_time=processing_time,
                complexity_level=result.get('complexity_level', 'Unknown'),
                created_at=datetime.now()
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
        logger.error(f"❌ Failed to evaluate case {case_data.get('case_id', 'unknown')}: {e}")
        
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

@celery_app.task(bind=True, name='evaluation_tasks.run_batch_evaluation')
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
        
        # Update job status to running
        with get_db_session() as db:
            job = db.query(TestJob).filter(TestJob.id == job_id).first()
            if job:
                job.status = 'running'
                job.start_time = datetime.now()
                db.commit()
        
        results = []
        successful_cases = 0
        failed_cases = 0
        
        for i, case_data in enumerate(case_list, 1):
            try:
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
                
                # Evaluate single case
                result = run_single_case_evaluation(case_data, job_id)
                
                if result.get('success'):
                    successful_cases += 1
                    results.append(result)
                    logger.info(f"✅ Case {i}/{total_cases} completed")
                else:
                    failed_cases += 1
                    logger.error(f"❌ Case {i}/{total_cases} failed: {result.get('error')}")
                    
            except Exception as e:
                failed_cases += 1
                logger.error(f"❌ Case {i}/{total_cases} failed with exception: {e}")
                results.append({
                    'success': False,
                    'case_id': case_data.get('case_id'),
                    'error': str(e)
                })
        
        # Update job completion
        with get_db_session() as db:
            job = db.query(TestJob).filter(TestJob.id == job_id).first()
            if job:
                job.status = 'completed'
                job.end_time = datetime.now()
                job.processed_cases = successful_cases
                job.total_cases = total_cases
                db.commit()
        
        # Calculate summary statistics
        total_score = sum(r.get('overall_score', 0) for r in results if r.get('success'))
        average_score = total_score / successful_cases if successful_cases > 0 else 0
        
        logger.info(f"🎉 Batch evaluation completed!")
        logger.info(f"📊 Success: {successful_cases}, Failed: {failed_cases}")
        logger.info(f"📈 Average Score: {average_score:.2f}")
        
        return {
            'success': True,
            'job_id': job_id,
            'total_cases': total_cases,
            'successful_cases': successful_cases,
            'failed_cases': failed_cases,
            'average_score': round(average_score, 2),
            'results': results,
            'task_id': self.request.id
        }
        
    except Exception as e:
        logger.error(f"❌ Batch evaluation failed for job {job_id}: {e}")
        
        # Update job status to failed
        with get_db_session() as db:
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

@celery_app.task(name='evaluation_tasks.get_evaluation_status')
def get_evaluation_status(job_id: str) -> Dict[str, Any]:
    """
    Get the current status of an evaluation job
    
    Args:
        job_id: ID of the evaluation job
        
    Returns:
        Dictionary with job status information
    """
    try:
        with get_db_session() as db:
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
        logger.error(f"❌ Failed to get status for job {job_id}: {e}")
        return {'error': str(e)}