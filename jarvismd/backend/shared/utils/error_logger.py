"""
Centralized Error Logging Utility
Provides full traceback logging with context for easier debugging
"""

import traceback
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

def log_full_error(
    error: Exception, 
    context: Optional[Dict[str, Any]] = None,
    log_level: str = "error"
) -> None:
    """
    Log full traceback with context information for easier debugging
    
    Args:
        error: The exception that occurred
        context: Optional dictionary with additional context 
                 (e.g., {'job_id': '123', 'case_id': '456', 'function': 'evaluate_single_case'})
        log_level: Logging level ('error', 'warning', 'critical', 'debug')
    """
    error_type = type(error).__name__
    error_message = str(error)
    full_traceback = traceback.format_exc()
    timestamp = datetime.now().isoformat()
    
    # Build structured log message
    log_parts = [
        f"❌ ERROR: {error_type}",
        f"📝 Message: {error_message}",
        f"🕐 Timestamp: {timestamp}"
    ]
    
    # Add context if provided
    if context:
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        log_parts.append(f"📋 Context: {context_str}")
    
    # Add full traceback
    log_parts.append(f"📜 Full Traceback:\n{full_traceback}")
    
    # Join all parts
    full_log_message = "\n".join(log_parts)
    
    # Log at appropriate level
    log_func = getattr(logger, log_level.lower(), logger.error)
    log_func(full_log_message)

