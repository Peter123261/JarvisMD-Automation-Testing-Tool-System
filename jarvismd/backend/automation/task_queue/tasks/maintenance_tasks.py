"""
Celery Tasks for System Maintenance and Monitoring
Handles system health checks, cleanup, and performance monitoring
"""

import os
import sys
import logging
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List
from celery import current_task

# Import Celery app and database components using proper package imports
from celery import current_app
from jarvismd.backend.database.database import get_session
from jarvismd.backend.database.models import TestJob, EvaluationResult, MaintenanceReport
from jarvismd.backend.automation.task_queue.config.redis_config import get_redis_config

logger = logging.getLogger(__name__)

@current_app.task(name='maintenance_tasks.system_health_check')
def system_health_check() -> Dict[str, Any]:
    """
    Perform comprehensive system health check
    
    Returns:
        Dictionary with system health metrics
    """
    try:
        logger.info("🔍 Starting system health check...")
        
        # System resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Database health
        db_healthy = False
        try:
            with get_session() as db:
                from sqlalchemy import text
                db.execute(text("SELECT 1"))
                db_healthy = True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
        
        # Redis health
        redis_healthy = False
        try:
            redis_config = get_redis_config()
            client = redis_config.get_client()
            client.ping()
            redis_healthy = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
        
        # Active jobs count
        active_jobs = 0
        try:
            with get_session() as db:  # ← CORRECTED
                active_jobs = db.query(TestJob).filter(
                    TestJob.status.in_(['pending', 'running'])
                ).count()
        except Exception as e:
            logger.error(f"Failed to count active jobs: {e}")
        
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'system_resources': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': round(memory.available / (1024**3), 2),
                'disk_percent': disk.percent,
                'disk_free_gb': round(disk.free / (1024**3), 2)
            },
            'services': {
                'database': db_healthy,
                'redis': redis_healthy
            },
            'workload': {
                'active_jobs': active_jobs
            },
            'overall_health': 'healthy' if (db_healthy and redis_healthy and cpu_percent < 90 and memory.percent < 90) else 'warning'
        }
        
        logger.info(f"✅ System health check completed: {health_status['overall_health']}")
        
        # Save report to database
        try:
            with get_session() as db:
                report = MaintenanceReport(
                    report_type='health_check',
                    report_data=health_status,
                    overall_status=health_status['overall_health'],
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    disk_percent=disk.percent,
                    active_jobs=active_jobs,
                    task_id=current_task.request.id if current_task else None
                )
                db.add(report)
                db.commit()
                logger.info("📝 Health report saved to database")
        except Exception as save_error:
            logger.warning(f"⚠️ Could not save health report: {save_error}")
        
        return health_status
        
    except Exception as e:
        logger.error(f"❌ System health check failed: {e}")
        error_status = {
            'timestamp': datetime.now().isoformat(),
            'overall_health': 'error',
            'error': str(e)
        }
        
        # Try to save error report
        try:
            with get_session() as db:
                report = MaintenanceReport(
                    report_type='health_check',
                    report_data=error_status,
                    overall_status='error',
                    task_id=current_task.request.id if current_task else None
                )
                db.add(report)
                db.commit()
        except:
            pass
        
        return error_status

@current_app.task(name='maintenance_tasks.archive_old_jobs')
def archive_old_jobs(days_old: int = 3) -> Dict[str, Any]:
    """
    Archive (not delete) completed jobs older than specified days
    Marks jobs as archived and exports to JSON for long-term storage
    
    Args:
        days_old: Number of days - jobs older than this will be archived (default: 3)
        
    Returns:
        Dictionary with archival results
    """
    try:
        logger.info(f"📦 Starting archival of jobs older than {days_old} days...")
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        with get_session() as db:
            # Find completed jobs older than cutoff
            old_jobs = db.query(TestJob).filter(
                TestJob.status == 'completed',
                TestJob.end_time < cutoff_date
            ).all()
            
            archived_count = 0
            archived_jobs = []
            
            for job in old_jobs:
                # Get associated results
                results = db.query(EvaluationResult).filter(
                    EvaluationResult.test_job_id == job.id
                ).all()
                
                # Create archive record
                archive_data = {
                    'job_id': job.id,
                    'benchmark': job.benchmark,
                    'model': job.model,
                    'total_cases': job.total_cases,
                    'average_score': sum(r.total_score for r in results) / len(results) if results else 0,
                    'completed_at': job.end_time.isoformat() if job.end_time else None,
                    'result_count': len(results)
                }
                
                archived_jobs.append(archive_data)
                archived_count += 1
            
            # Note: Jobs are NOT deleted, just marked for archival tracking
            # You can add a 'archived' field to TestJob model if you want to mark them
            
            archive_result = {
                'timestamp': datetime.now().isoformat(),
                'cutoff_date': cutoff_date.isoformat(),
                'days_old': days_old,
                'archived_jobs': archived_count,
                'jobs_summary': archived_jobs
            }
            
            logger.info(f"✅ Archived {archived_count} jobs older than {days_old} days")
            return archive_result
        
    except Exception as e:
        logger.error(f"❌ Archival task failed: {e}")
        return {
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }

@current_app.task(name='maintenance_tasks.get_worker_statistics')
def get_worker_statistics() -> Dict[str, Any]:
    """
    Collect worker performance and task statistics
    
    Returns:
        Dictionary with worker statistics
    """
    try:
        logger.info("📊 Collecting worker statistics...")
        
        with get_session() as db:  # ← CORRECTED
            # Job statistics
            total_jobs = db.query(TestJob).count()
            completed_jobs = db.query(TestJob).filter(TestJob.status == 'completed').count()
            failed_jobs = db.query(TestJob).filter(TestJob.status == 'failed').count()
            running_jobs = db.query(TestJob).filter(TestJob.status == 'running').count()
            
            # Result statistics
            total_results = db.query(EvaluationResult).count()
            
            # Average processing time
            from sqlalchemy import func
            avg_processing_time = db.query(
                func.avg(EvaluationResult.processing_time)
            ).scalar() or 0
            
            # Recent activity (last 24 hours)
            yesterday = datetime.now() - timedelta(days=1)
            recent_jobs = db.query(TestJob).filter(
                TestJob.start_time >= yesterday
            ).count()
            
            recent_results = db.query(EvaluationResult).filter(
                EvaluationResult.created_at >= yesterday
            ).count()
        
        statistics = {
            'timestamp': datetime.now().isoformat(),
            'jobs': {
                'total': total_jobs,
                'completed': completed_jobs,
                'failed': failed_jobs,
                'running': running_jobs,
                'success_rate': round((completed_jobs / total_jobs * 100), 2) if total_jobs > 0 else 0
            },
            'results': {
                'total': total_results,
                'recent_24h': recent_results
            },
            'performance': {
                'avg_processing_time_seconds': round(avg_processing_time, 2),
                'recent_jobs_24h': recent_jobs
            }
        }
        
        logger.info(f"✅ Statistics collected: {total_jobs} jobs, {total_results} results")
        return statistics
        
    except Exception as e:
        logger.error(f"❌ Failed to collect statistics: {e}")
        return {
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }

@current_app.task(name='maintenance_tasks.daily_maintenance')
def daily_maintenance() -> Dict[str, Any]:
    """
    Run daily system maintenance tasks
    
    Returns:
        Dictionary with maintenance results
    """
    try:
        logger.info("🔧 Starting daily maintenance...")
        
        maintenance_results = {
            'timestamp': datetime.now().isoformat(),
            'tasks': {}
        }
        
        # Run health check
        try:
            health_result = system_health_check()
            maintenance_results['tasks']['health_check'] = health_result
        except Exception as e:
            maintenance_results['tasks']['health_check'] = {'error': str(e)}
        
        # Run archival (manual trigger only, not in daily maintenance)
        # Archival is intentionally manual to prevent accidental data loss
        
        # Collect statistics
        try:
            stats_result = get_worker_statistics()
            maintenance_results['tasks']['statistics'] = stats_result
        except Exception as e:
            maintenance_results['tasks']['statistics'] = {'error': str(e)}
        
        logger.info("✅ Daily maintenance completed")
        
        # Save maintenance report to database
        try:
            with get_session() as db:
                # Extract overall status from health check
                health_status = maintenance_results['tasks'].get('health_check', {})
                overall_status = health_status.get('overall_health', 'unknown')
                
                report = MaintenanceReport(
                    report_type='daily_maintenance',
                    report_data=maintenance_results,
                    overall_status=overall_status,
                    cpu_percent=health_status.get('system_resources', {}).get('cpu_percent'),
                    memory_percent=health_status.get('system_resources', {}).get('memory_percent'),
                    disk_percent=health_status.get('system_resources', {}).get('disk_percent'),
                    active_jobs=health_status.get('workload', {}).get('active_jobs'),
                    task_id=current_task.request.id if current_task else None
                )
                db.add(report)
                db.commit()
                logger.info("📝 Daily maintenance report saved to database")
        except Exception as save_error:
            logger.warning(f"⚠️ Could not save maintenance report: {save_error}")
        
        return maintenance_results
        
    except Exception as e:
        logger.error(f"❌ Daily maintenance failed: {e}")
        error_result = {
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }
        
        # Try to save error report
        try:
            with get_session() as db:
                report = MaintenanceReport(
                    report_type='daily_maintenance',
                    report_data=error_result,
                    overall_status='error',
                    task_id=current_task.request.id if current_task else None
                )
                db.add(report)
                db.commit()
        except:
            pass
        
        return error_result