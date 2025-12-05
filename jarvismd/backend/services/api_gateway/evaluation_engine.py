"""
Optimized Evaluation Engine for JarvisMD Automation Testing Tool
Implements cost-efficient LLM evaluation with smart resource management
"""

import os
import json
import re
import logging
import time
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
from contextlib import asynccontextmanager

# Python 3.10+ compatibility fix for collections
import sys
if sys.version_info >= (3, 10):
    import collections.abc
    collections.MutableSet = collections.abc.MutableSet
    collections.MutableMapping = collections.abc.MutableMapping
    collections.MutableSequence = collections.abc.MutableSequence
    collections.Iterable = collections.abc.Iterable
    collections.Mapping = collections.abc.Mapping
    collections.Sequence = collections.abc.Sequence

# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge, start_http_server  # type: ignore

# OpenTelemetry imports
from opentelemetry import trace  # type: ignore
from opentelemetry.trace import Status, StatusCode  # type: ignore

# LangChain imports
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Local imports
try:
    from .paths import PROMPTS_DIR, ensure_directories
    from .settings import settings
except ImportError:
    pass  # Ensure except block has body
    # Fallback for direct execution
    from paths import PROMPTS_DIR, ensure_directories
    from settings import settings

# Centralized error logging
try:
    from jarvismd.backend.shared.utils.error_logger import log_full_error
except ImportError:
    # Fallback if import fails
    def log_full_error(error: Exception, context: dict = None, log_level: str = "error"):
        """Fallback error logger if import fails"""
        logger.error(f"Error: {type(error).__name__}: {str(error)}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")

logger = logging.getLogger(__name__)

# OpenTelemetry tracer
tracer = trace.get_tracer(__name__)

# Prometheus metrics setup
EVALUATION_COUNTER = Counter('evaluations_total', 'Total number of evaluations')
EVALUATION_DURATION = Histogram('evaluation_duration_seconds', 'Time spent on evaluations', buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0])
EVALUATION_SUCCESS_RATE = Gauge('evaluation_success_rate', 'Success rate of evaluations (0-1)')
CASES_FLAGGED = Counter('cases_flagged_total', 'Total cases flagged for review')

# Additional application metrics for success/failure and token usage
EVALUATIONS_SUCCESS_TOTAL = Counter('evaluations_success_total', 'Total successful evaluations')
EVALUATIONS_FAILED_TOTAL = Counter('evaluations_failed_total', 'Total failed evaluations')

TOKENS_INPUT_TOTAL = Counter('tokens_input_total', 'Total input tokens processed')
TOKENS_OUTPUT_TOTAL = Counter('tokens_output_total', 'Total output tokens generated')
TOKENS_TOTAL = Counter('tokens_total', 'Total tokens processed (input + output)')

@dataclass
class UsageMetrics:
    """Track API usage and performance metrics"""
    total_calls: int = 0
    total_tokens: int = 0
    
    # Performance metrics
    total_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    successful_calls: int = 0
    failed_calls: int = 0
    
    def add_call(self, tokens_used: int = 1000, duration: float = 0.0, success: bool = True):
        """Add a new API call to metrics with performance data"""
        self.total_calls += 1
        self.total_tokens += tokens_used
        
        # Performance tracking
        self.total_duration += duration
        self.min_duration = min(self.min_duration, duration)
        self.max_duration = max(self.max_duration, duration)
        
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        avg_duration = self.total_duration / max(1, self.total_calls)
        success_rate = (self.successful_calls / max(1, self.total_calls)) * 100
        
        return {
            "total_calls": self.total_calls,
            "total_tokens": self.total_tokens,
            "average_tokens_per_call": self.total_tokens // max(1, self.total_calls),
            # Performance metrics
            "total_duration": round(self.total_duration, 2),
            "average_duration": round(avg_duration, 2),
            "min_duration": round(self.min_duration, 2) if self.min_duration != float('inf') else 0,
            "max_duration": round(self.max_duration, 2),
            "success_rate": round(success_rate, 2),
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls
        }

class EvaluationEngine:
    """
    Optimized evaluation engine with singleton pattern for resource efficiency
    """
    
    _instance = None
    _llm = None
    _prompt_template = None
    _usage_metrics = None
    _prompt_path = None
    
    def __new__(cls, prompt_path: Optional[Path] = None):
        """Singleton pattern - only one instance allowed"""
        if cls._instance is None:
            cls._instance = super(EvaluationEngine, cls).__new__(cls)
            cls._instance._initialized = False
        # Store prompt_path for later use in __init__
        if prompt_path:
            cls._instance._pending_prompt_path = prompt_path
        return cls._instance
    
    def __init__(self, prompt_path: Optional[Path] = None):
        """
        Initialize the evaluation engine (only once)
        
        Args:
            prompt_path: Optional path to prompt file. If not provided, prompt will be loaded per evaluation.
        """
        # Get prompt_path from __new__ if it was passed there
        if hasattr(self, '_pending_prompt_path'):
            prompt_path = self._pending_prompt_path
            delattr(self, '_pending_prompt_path')
        
        if self._initialized:
            pass  # Ensure if block has body
            # If already initialized but new prompt_path provided, update it
            if prompt_path and prompt_path != self._prompt_path:
                self._prompt_path = prompt_path
                self._prompt_template = None  # Force reload on next evaluation
            return
            
        logger.info("🚀 Initializing Optimized Evaluation Engine...")
        
        # Initialize usage tracking
        self._usage_metrics = UsageMetrics()
        
        # Ensure directories exist
        ensure_directories()
        
        # Store prompt path (will be loaded on first evaluation if provided)
        self._prompt_path = prompt_path
        
        # Initialize LLM (lazy loading)
        self._llm = None
        
        # Start Prometheus metrics server (if not already started)
        self._start_metrics_server()
        
        self._initialized = True
        logger.info("✅ Evaluation Engine initialized successfully")
    
    def _start_metrics_server(self):
        """Start Prometheus metrics server on port 8001"""
        try:
            start_http_server(8001)
            logger.info("📊 Prometheus metrics server started on port 8001")
        except Exception as e:
            logger.warning(f"⚠️ Could not start metrics server: {e}")
    
    def _load_prompt_template(self, prompt_path: Optional[Path] = None):
        """
        Load prompt template from specified path or use cached instance
        
        Args:
            prompt_path: Path to prompt file. If None, uses self._prompt_path or raises error.
        """
        # Use provided path, or fall back to instance path
        path_to_use = prompt_path or self._prompt_path
        
        if not path_to_use:
            raise ValueError("Prompt path must be provided either in __init__ or _load_prompt_template")
        
        # If template already loaded for this path, return cached version
        if self._prompt_template is not None and path_to_use == self._prompt_path:
            return
        
        try:
            if not path_to_use.exists():
                raise FileNotFoundError(f"Prompt file not found: {path_to_use}")
            
            with open(path_to_use, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            self._prompt_template = PromptTemplate(
                template=template_content,
                input_variables=["summary", "recommendation"]
            )
            self._prompt_path = path_to_use
            logger.info(f"✅ Prompt template loaded from: {path_to_use.name}")
                
        except Exception as e:
            log_full_error(e, context={'function': '_load_prompt_template', 'prompt_path': str(path_to_use)})
            raise
    
    def _get_llm(self):
        """Get LLM instance (lazy loading)"""
        if self._llm is None:
            logger.info("🔧 Creating LLM instance...")
            self._llm = ChatOpenAI(
                model=settings.default_model,
                temperature=settings.model_temperature,
                api_key=settings.openai_api_key
            )
            logger.info("✅ LLM instance created and cached")
        
        return self._llm
    
    def evaluate_single_case(self, summary: str, recommendation: str, prompt_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Evaluate a single medical case with optimized resource usage
        
        Args:
            summary: Medical case summary
            recommendation: LLM recommendation to evaluate
            prompt_path: Optional path to prompt file. If provided, will load/use this prompt.
                        If not provided, uses the prompt_path from __init__.
            
        Returns:
            Evaluation result with scores and feedback
        """
        start_time = time.time()
        success = False
        trace_id = None
        
        # Start OpenTelemetry span for this evaluation
        with tracer.start_as_current_span("evaluate_single_case") as span:
            try:
                pass  # Ensure try block has body
                # Get trace ID for database storage
                # Try multiple methods to get trace_id with full traceback logging
                trace_id = None
                
                # Method 1: Try to get from the span itself
                try:
                    logger.info("🔍 Attempting Method 1: Getting trace_id from span.get_span_context()")
                    span_context = span.get_span_context()
                    logger.info(f"🔍 Span context retrieved: {span_context}, is_valid: {span_context.is_valid if span_context else 'None'}")
                    if span_context and span_context.is_valid:
                        trace_id = format(span_context.trace_id, '032x')
                        span.set_attribute("trace_id", trace_id)
                        logger.info(f"📊 Trace ID generated from span: {trace_id}")
                    else:
                        logger.warning(f"⚠️ Span context invalid or None. span_context={span_context}, is_valid={span_context.is_valid if span_context else 'N/A'}")
                except Exception as e:
                    log_full_error(e, context={'function': 'evaluate_single_case', 'method': 'span.get_span_context()'})
                
                # Method 2: Try to get from current span if Method 1 failed
                if not trace_id:
                    try:
                        logger.info("🔍 Attempting Method 2: Getting trace_id from trace.get_current_span()")
                        current_span = trace.get_current_span()
                        logger.info(f"🔍 Current span retrieved: {current_span}")
                        if current_span:
                            span_context = current_span.get_span_context()
                            logger.info(f"🔍 Current span context: {span_context}, is_valid: {span_context.is_valid if span_context else 'None'}")
                            if span_context and span_context.is_valid:
                                trace_id = format(span_context.trace_id, '032x')
                                span.set_attribute("trace_id", trace_id)
                                logger.info(f"📊 Trace ID generated from current span: {trace_id}")
                            else:
                                logger.warning(f"⚠️ Current span context invalid or None. span_context={span_context}, is_valid={span_context.is_valid if span_context else 'N/A'}")
                        else:
                            logger.warning("⚠️ trace.get_current_span() returned None")
                    except Exception as e:
                        log_full_error(e, context={'function': 'evaluate_single_case', 'method': 'trace.get_current_span()'})
                
                # Log warning if still no trace_id
                if not trace_id:
                    logger.warning("⚠️ Could not extract trace_id from OpenTelemetry span context after trying both methods")
                    logger.warning(f"⚠️ Span object: {span}, type: {type(span)}")
                    logger.warning(f"⚠️ Tracer object: {tracer}, type: {type(tracer)}")
                
                # Add attributes to span
                span.set_attribute("evaluation.summary_length", len(summary))
                span.set_attribute("evaluation.recommendation_length", len(recommendation))
                if prompt_path:
                    span.set_attribute("evaluation.prompt_file", prompt_path.name)
                
                logger.info("🔍 Evaluating single case...")
                
                # Load prompt template (will use cached if same path, or load new if different)
                self._load_prompt_template(prompt_path)
                
                # Use cached LLM instance for efficiency (singleton pattern)
                # Get or create LLM instance (lazy loading)
                llm = self._get_llm()
                
                # Add LLM model to span
                span.set_attribute("llm.model", getattr(llm, 'model_name', settings.default_model))
                
                # Create chain up to the LLM to preserve response metadata (token usage)
                llm_chain = (
                    {"summary": RunnablePassthrough(), "recommendation": RunnablePassthrough()}
                    | self._prompt_template
                    | llm  # Use cached instance
                )
                
                # Execute evaluation with tracing
                with tracer.start_as_current_span("llm_invoke") as llm_span:
                    ai_message = llm_chain.invoke({
                        "summary": summary,
                        "recommendation": recommendation
                    })
                    
                    # Extract raw text to check for content moderation
                    raw_text = getattr(ai_message, 'content', None) or str(ai_message)
                    
                    # Check for content moderation indicators
                    content_moderation_indicators = [
                        "I'm sorry, but I can't assist",
                        "I cannot assist",
                        "I can't help",
                        "content policy",
                        "safety guidelines"
                    ]
                    is_content_moderation = any(indicator.lower() in raw_text.lower() for indicator in content_moderation_indicators)
                    
                    # Add LLM response metadata to span
                    try:
                        response_meta = getattr(ai_message, 'response_metadata', None)
                        if response_meta and isinstance(response_meta, dict):
                            model_name = response_meta.get('model_name')
                            if model_name:
                                llm_span.set_attribute("llm.response_model", model_name)
                            
                            # Add token usage
                            usage = response_meta.get('token_usage') or response_meta.get('usage') or {}
                            if isinstance(usage, dict):
                                llm_span.set_attribute("llm.tokens.prompt", usage.get('prompt_tokens', 0))
                                llm_span.set_attribute("llm.tokens.completion", usage.get('completion_tokens', 0))
                                llm_span.set_attribute("llm.tokens.total", usage.get('total_tokens', 0))
                    except Exception:
                        pass  # Best effort
                    
                    # Mark span if content moderation detected
                    if is_content_moderation:
                        llm_span.set_attribute("llm.content_moderation", True)
                        llm_span.set_attribute("error", True)
                        llm_span.set_attribute("error.type", "content_moderation")
                        llm_span.set_attribute("error.message", "Content moderation triggered by LLM")
                
                # Extract model name from response metadata (automatically captured from OpenAI API)
                # Central and explicit extraction with no silent fallbacks
                model_used = None
                try:
                    pass  # Ensure try block has body
                    # Primary: Extract from response_metadata['model_name']
                    response_meta = getattr(ai_message, 'response_metadata', None)
                    if response_meta and isinstance(response_meta, dict):
                        model_used = response_meta.get('model_name')
                        if model_used:
                            logger.debug(f"✅ Extracted model from response_metadata: {model_used}")
                except (AttributeError, KeyError, TypeError) as e:
                    logger.debug(f"⚠️ Could not get model from response_metadata: {e}")
                
                # Fallback 1: Try LLM instance attributes
                if not model_used:
                    try:
                        model_used = getattr(llm, 'model_name', None) or getattr(llm, 'model', None)
                        if model_used:
                            logger.debug(f"✅ Extracted model from LLM instance: {model_used}")
                    except AttributeError:
                        pass
                
                # Fallback 2: Use settings default
                if not model_used:
                    model_used = settings.default_model
                    logger.debug(f"⚠️ Using default model from settings: {model_used}")
                
                # Store in a variable for clarity
                model_name = model_used

                # Parse result with tracing
                with tracer.start_as_current_span("parse_evaluation_result") as parse_span:
                    parsed_result = self._parse_evaluation_result(raw_text)
                    
                    # Check if parsing failed
                    if not parsed_result.get('success', True):
                        # Mark parse span as error
                        error_type = parsed_result.get('error_type', 'parsing_failed')
                        error_message = parsed_result.get('feedback', 'Parsing failed')
                        parse_span.set_status(Status(StatusCode.ERROR, error_message))
                        parse_span.set_attribute("error", True)
                        parse_span.set_attribute("error.type", error_type)
                        parse_span.set_attribute("error.message", error_message)
                        parse_span.record_exception(Exception(error_message))
                    else:
                        # Add parsing results to span (success case)
                        criteria_count = len(parsed_result.get('criteria_scores', {}))
                        parse_span.set_attribute("result.criteria_count", criteria_count)
                        parse_span.set_attribute("result.overall_score", parsed_result.get('overall_score', 0))
                
                # Calculate duration
                duration = time.time() - start_time
                success = parsed_result.get('success', True)  # Use actual parsing result
                
                # Add duration to span
                span.set_attribute("evaluation.duration_seconds", duration)
                
                # Set span status based on actual result
                if not success:
                    # Parsing failed - mark span as error
                    error_type = parsed_result.get('error_type', 'evaluation_failed')
                    error_message = parsed_result.get('feedback', 'Evaluation failed')
                    span.set_status(Status(StatusCode.ERROR, error_message))
                    span.set_attribute("error", True)
                    span.set_attribute("error.type", error_type)
                    span.set_attribute("error.message", error_message)
                else:
                    span.set_status(Status(StatusCode.OK))
                
                # Add duration to result
                parsed_result['processing_time'] = duration
                # Track metrics with performance data
                self._usage_metrics.add_call(duration=duration, success=success)
                
                # Update Prometheus metrics
                EVALUATION_COUNTER.inc()
                EVALUATION_DURATION.observe(duration)

                # Mark success
                EVALUATIONS_SUCCESS_TOTAL.inc()

                # Token usage export from AIMessage metadata when available
                # Tries common locations used by providers/LangChain wrappers
                token_usage_data = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
                try:
                    usage_meta = getattr(ai_message, 'response_metadata', None) or getattr(ai_message, 'generation_info', None) or {}
                    # Common keys: token_usage, usage
                    usage = (
                        (usage_meta.get('token_usage') if isinstance(usage_meta, dict) else None)
                        or (usage_meta.get('usage') if isinstance(usage_meta, dict) else None)
                        or {}
                    )
                    if isinstance(usage, dict):
                        input_tokens = int(usage.get('prompt_tokens', 0))
                        output_tokens = int(usage.get('completion_tokens', 0))
                        total_tokens = int(usage.get('total_tokens', input_tokens + output_tokens))
                        if input_tokens:
                            TOKENS_INPUT_TOTAL.inc(input_tokens)
                            token_usage_data["prompt_tokens"] = input_tokens
                        if output_tokens:
                            TOKENS_OUTPUT_TOTAL.inc(output_tokens)
                            token_usage_data["completion_tokens"] = output_tokens
                        if total_tokens:
                            TOKENS_TOTAL.inc(total_tokens)
                            token_usage_data["total_tokens"] = total_tokens
                except Exception:
                    pass  # Ensure except block has body
                    # Best-effort: absence of token metadata should never break evaluation

                parsed_result['token_usage'] = token_usage_data
                parsed_result['model_used'] = model_name  # Add model name from API response
                
                # Check if case should be flagged for review
                overall_score = parsed_result.get('overall_score', 0)
                span.set_attribute("result.flagged", overall_score < 75)
                if overall_score < 75:
                    CASES_FLAGGED.inc()
                    parsed_result['flagged_for_review'] = True
                    parsed_result['review_priority'] = 'high' if overall_score < 50 else 'medium'
                else:
                    parsed_result['flagged_for_review'] = False
                    parsed_result['review_priority'] = 'none'
                
                # Update success rate
                success_rate = self._usage_metrics.successful_calls / max(1, self._usage_metrics.total_calls)
                EVALUATION_SUCCESS_RATE.set(success_rate)
                
                logger.info(f"✅ Case evaluated successfully (Call #{self._usage_metrics.total_calls}, Duration: {duration:.2f}s)")
                parsed_result['trace_id'] = trace_id  # Store trace ID in result
                return parsed_result
            except Exception as e:
                duration = time.time() - start_time
                success = False
                
                # Mark span as error
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                
                # Track failed evaluation
                self._usage_metrics.add_call(duration=duration, success=success)
                EVALUATION_COUNTER.inc()
                EVALUATION_DURATION.observe(duration)
                EVALUATIONS_FAILED_TOTAL.inc()
                
                # Update success rate
                success_rate = self._usage_metrics.successful_calls / max(1, self._usage_metrics.total_calls)
                EVALUATION_SUCCESS_RATE.set(success_rate)
                
                # Classify the error type from the actual exception
                error_type = type(e).__name__
                error_message = str(e)
                
                # Log detailed error information with full traceback
                pass  
                log_full_error(
                    e,
                    context={
                        'function': 'evaluate_single_case',
                        'error_type': error_type,
                        'is_openai_error': 'openai' in error_type.lower() or 'api' in error_type.lower()
                    }
                )
                
                # Check if this is an OpenAI API error
                if 'openai' in error_type.lower() or 'api' in error_type.lower():
                    pass  # Ensure if block has body
                    logger.error(f"OpenAI API Error detected")
                
                # Get trace_id from current span even in error case
                error_trace_id = None
                try:
                    current_span = trace.get_current_span()
                    if current_span:
                        span_context = current_span.get_span_context()
                        if span_context and span_context.is_valid:
                            error_trace_id = format(span_context.trace_id, '032x')
                except Exception:
                    pass  # Ensure except block has body
                
                # Return error result instead of raising (for better error handling)
                return {
                    'success': False,
                    'error_type': error_type,
                    'error_message': error_message,
                    'timestamp': datetime.now().isoformat(),
                    'raw_result': '',
                    'scores': {},
                    'feedback': f"Evaluation failed: {error_type} - {error_message}",
                    'overall_score': 0,
                    'complexity_level': 'Unknown',
                    'recommendations': [],
                    'processing_time': duration,
                    'trace_id': error_trace_id  # Include trace_id even in error case
                }
    
    def evaluate_batch(self, cases: List[Dict[str, str]], prompt_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Evaluate multiple cases efficiently
        
        Args:
            cases: List of cases with 'summary' and 'recommendation' keys
            prompt_path: Optional path to prompt file. If provided, will use this prompt for all cases.
            
        Returns:
            List of evaluation results
        """
        logger.info(f"🔍 Evaluating batch of {len(cases)} cases...")
        
        results = []
        for i, case in enumerate(cases, 1):
            try:
                result = self.evaluate_single_case(
                    case['summary'], 
                    case['recommendation'],
                    prompt_path=prompt_path
                )
                result['case_id'] = case.get('case_id', f'case_{i}')
                results.append(result)
                
                logger.info(f"✅ Case {i}/{len(cases)} completed")
                
            except Exception as e:
                log_full_error(
                    e,
                    context={
                        'function': 'evaluate_batch',
                        'case_index': i,
                        'case_id': case.get('case_id', f'case_{i}'),
                        'total_cases': len(cases)
                    }
                )
                results.append({
                    'case_id': case.get('case_id', f'case_{i}'),
                    'error': str(e),
                    'success': False
                })
        
        logger.info(f"✅ Batch evaluation completed: {len(results)} results")
        return results
    
    def _parse_evaluation_result(self, raw_result: str) -> Dict[str, Any]:
        """
        Parse the raw LLM evaluation result into structured format with comprehensive validation
        
        Args:
            raw_result: Raw text from LLM
            
        Returns:
            Parsed evaluation result with validation safeguards
        """
        try:
            pass  # Ensure try block has body
            # Log the raw result for debugging
            logger.info(f"🔍 Raw AI response (full): {raw_result}")
            
            # Try to extract JSON from the result
            json_match = re.search(r'\{.*\}', raw_result, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)
                
                # Extract the real evaluation scores from the AI response
                overall_score = 0
                detailed_scores = {}
                validation_results = {}
                
                # Extract individual criteria scores FIRST (source of truth)
                # Store with criterion ID as key (not name) for reliable lookup
                if 'criteria' in parsed:
                    for criterion in parsed['criteria']:
                        if isinstance(criterion, dict):
                            criterion_id = criterion.get('id')
                            criterion_score = criterion.get('score', 0)
                            
                            # Use ID as key for consistent lookup
                            if criterion_id is not None:
                                criterion_id_int = int(criterion_id)
                                detailed_scores[str(criterion_id_int)] = {
                                    'score': criterion_score,
                                    'id': criterion_id_int
                                }
                            else:
                                pass  # Ensure else block has body
                                # Fallback: use name if ID is missing (shouldn't happen)
                                criterion_name = criterion.get('criterion', f"criterion_{criterion.get('id', 'unknown')}")
                                detailed_scores[criterion_name] = criterion_score
                
                # Calculate overall_score from actual criteria scores (not LLM's declared score)
                # This ensures accuracy regardless of what the LLM claims
                from .utils import get_criterion_score
                calculated_sum = sum(get_criterion_score(score_data) for score_data in detailed_scores.values())
                
                # Get max possible score dynamically from prompt parser (source of truth)
                # Fall back to LLM's declared value or calculate from score ranges if needed
                max_possible_score = None
                
                # First, try to calculate from actual score ranges (most accurate)
                score_ranges = self._get_score_ranges()
                if score_ranges:
                    calculated_max = sum(score_ranges.values())
                    max_possible_score = calculated_max
                    logger.debug(f"✅ Calculated max_possible_score from prompt: {calculated_max}")
                
                # Fallback: Use LLM's declared value if calculation failed
                if max_possible_score is None:
                    if 'final_validation' in parsed:
                        final_val = parsed['final_validation']
                        llm_declared_max = final_val.get('maximum_possible_score')
                        if llm_declared_max:
                            max_possible_score = float(llm_declared_max)
                            logger.debug(f"✅ Using LLM-declared max_possible_score: {max_possible_score}")
                        else:
                            pass  # Ensure else block has body
                            # Try to recalculate from score_ranges as fallback
                            try:
                                score_ranges_fallback = self._get_score_ranges()
                                if score_ranges_fallback:
                                    max_possible_score = sum(score_ranges_fallback.values())
                                    logger.debug(f"✅ Recalculated max_possible_score from score_ranges: {max_possible_score}")
                            except Exception as e:
                                log_full_error(e, context={'function': '_parse_evaluation_result', 'operation': 'calculate_max_possible_score_fallback'})
                                max_possible_score = None
                    else:
                        pass  # Ensure else block has body
                        # Try to recalculate from score_ranges as last resort
                        try:
                            score_ranges_fallback = self._get_score_ranges()
                            if score_ranges_fallback:
                                max_possible_score = sum(score_ranges_fallback.values())
                                logger.debug(f"✅ Calculated max_possible_score from score_ranges (fallback): {max_possible_score}")
                            else:
                                logger.error("❌ Could not calculate max_possible_score: score_ranges is empty")
                                max_possible_score = None
                        except Exception as e:
                            log_full_error(e, context={'function': '_parse_evaluation_result', 'operation': 'calculate_max_possible_score_last_resort'})
                            max_possible_score = None
                
                # Calculate percentage from actual scores
                if max_possible_score > 0:
                    overall_score = (calculated_sum / max_possible_score) * 100
                else:
                    overall_score = 0
                
                # CRITICAL VALIDATION: Apply comprehensive safeguards
                validation_results = self._validate_evaluation_scores(parsed, detailed_scores, overall_score)
                
                # Update the parsed JSON to reflect the corrected scores before storing
                # This ensures downloaded JSON shows accurate scores
                if 'final_validation' in parsed:
                    parsed['final_validation']['final_score'] = calculated_sum
                    parsed['final_validation']['maximum_possible_score'] = max_possible_score
                    if max_possible_score > 0:
                        parsed['final_validation']['final_percentage'] = f"{overall_score:.0f}%"
                
                if 'evaluation_summary' in parsed:
                    parsed['evaluation_summary']['overall_score'] = f"{int(calculated_sum)}/{int(max_possible_score)}"
                    if max_possible_score > 0:
                        parsed['evaluation_summary']['overall_percentage'] = f"{overall_score:.0f}%"
                
                # Extract complexity level from complexity_assessment
                complexity_level = "Unknown"
                if 'complexity_assessment' in parsed:
                    complexity_data = parsed['complexity_assessment']
                    if isinstance(complexity_data, dict):
                        complexity_level = complexity_data.get('complexity_level', 'Unknown')
                    elif isinstance(complexity_data, str):
                        complexity_level = complexity_data
                
                result = {
                    'success': True,
                    'timestamp': datetime.now().isoformat(),
                    'raw_result': raw_result,
                    'scores': detailed_scores,
                    'feedback': json.dumps(parsed, indent=2),  # Full structured response
                    'overall_score': validation_results.get('validated_overall_score', overall_score),
                    'complexity_level': complexity_level,
                    'recommendations': parsed.get('recommendations', []),
                    'validation_results': validation_results  # Include validation audit trail
                }
                
                return result
            else:
                pass  # Ensure else block has body
                # NO JSON FOUND - This means OpenAI didn't provide a structured evaluation
                # This could be due to content policy, overloaded systems, or other issues
                logger.error(f"❌ PARSING FAILED - No valid JSON evaluation found in response")
                logger.error(f"📄 Raw response (first 500 chars): {raw_result[:500]}")
                logger.error(f"📄 Raw response (last 500 chars): {raw_result[-500:]}")
                logger.error(f"📊 Response length: {len(raw_result)} characters")
                
                # Classify based on response characteristics (not hardcoded strings)
                error_type = "invalid_response_format"
                
                if len(raw_result.strip()) == 0:
                    error_type = "empty_response"
                elif len(raw_result) < 100:
                    pass  # Ensure elif block has body
                    # Very short responses are usually refusals or errors
                    error_type = "truncated_response"
                
                logger.error(f"🚨 Response classification: {error_type}")
                
                return {
                    'success': False,  # ✅ CORRECTLY REPORT FAILURE
                    'error_type': error_type,
                    'timestamp': datetime.now().isoformat(),
                    'raw_result': raw_result,
                    'scores': {},
                    'feedback': f"EVALUATION FAILED: {error_type}. OpenAI response did not contain valid evaluation JSON. Raw response: {raw_result[:200]}",
                    'overall_score': 0,
                    'complexity_level': 'Unknown',
                    'recommendations': [],
                    'parse_error': 'No valid JSON found in response'
                }
                
        except Exception as e:
            log_full_error(
                e,
                context={
                    'function': '_parse_evaluation_result',
                    'raw_result_length': len(raw_result) if raw_result else 0,
                    'raw_result_preview': raw_result[:500] if raw_result else 'None'
                }
            )
            logger.error(f"📄 Raw response (first 500 chars): {raw_result[:500] if raw_result else 'None'}")
            logger.error(f"📄 Raw response (last 500 chars): {raw_result[-500:] if raw_result else 'None'}")
            
            return {
                'success': False,  # ✅ CORRECTLY REPORT FAILURE
                'error_type': 'parsing_exception',
                'timestamp': datetime.now().isoformat(),
                'raw_result': raw_result if raw_result else '',
                'scores': {},
                'feedback': f"PARSING EXCEPTION: {str(e)}",
                'overall_score': 0,
                'complexity_level': 'Unknown',
                'recommendations': [],
                'parse_warning': str(e),
                'exception_type': type(e).__name__
            }
    
    def _validate_evaluation_scores(self, parsed_response: Dict, detailed_scores: Dict, overall_score: float) -> Dict[str, Any]:
        """
        Comprehensive validation of evaluation scores to prevent under/over scoring
        
        Args:
            parsed_response: Full parsed AI response
            detailed_scores: Individual criteria scores
            overall_score: Calculated overall score
            
        Returns:
            Validation results with corrections and audit trail
        """
        validation_results = {
            'validation_passed': True,
            'issues_found': [],
            'corrections_made': [],
            'validated_scores': {},
            'validated_overall_score': overall_score,
            'audit_trail': []
        }
        
        # SAFEGUARD 1: Score Range Validator
        score_ranges = self._get_score_ranges()
        corrected_scores = {}
        
        # Import helpers locally to avoid circular import issues at module load
        from .utils import get_criterion_score, validate_criterion_score

        for criterion_key, score_data in detailed_scores.items():
            pass  # Ensure for block has body
            # Try to extract numeric score regardless of structure
            raw_score = get_criterion_score(score_data)

            # Determine criterion_id for max lookup
            criterion_id = None
            if isinstance(score_data, dict):
                criterion_id = score_data.get('id')
            if criterion_id is None:
                try:
                    criterion_id = int(criterion_key)
                except (ValueError, TypeError):
                    criterion_id = self._extract_criterion_id(parsed_response, criterion_key)

            # Get max_score from score_ranges (no hardcoded fallback - must exist in prompt)
            if not criterion_id:
                error_msg = f"Could not determine criterion_id for key: {criterion_key}"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            if criterion_id not in score_ranges:
                error_msg = f"Criterion {criterion_id} not found in score ranges. Available criteria: {list(score_ranges.keys())}"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            max_score = score_ranges[criterion_id]

            # Clamp/validate the score
            valid_score = validate_criterion_score(raw_score, max_score)

            # Record corrections if any
            if valid_score != raw_score:
                validation_results['corrections_made'].append(f"Corrected criterion {criterion_id}: {raw_score} → {valid_score}")
                if raw_score < 0:
                    validation_results['issues_found'].append(f"Criterion {criterion_id}: Score {raw_score} below minimum (0)")
                elif raw_score > max_score:
                    validation_results['issues_found'].append(f"Criterion {criterion_id}: Score {raw_score} exceeds maximum ({max_score})")

            # Preserve structure but with validated score
            if isinstance(score_data, dict):
                new_entry = dict(score_data)
                new_entry['score'] = valid_score
                if criterion_id is not None:
                    new_entry.setdefault('id', criterion_id)
                corrected_scores[criterion_key] = new_entry
            else:
                corrected_scores[criterion_key] = valid_score
        
        validation_results['validated_scores'] = corrected_scores
        
        # SAFEGUARD 2: Completeness Checker (Flexible)
        criteria_in_response = len(detailed_scores)
        expected_criteria = self._determine_expected_criteria_count(parsed_response)
        
        if criteria_in_response != expected_criteria:
            validation_results['issues_found'].append(f"Expected {expected_criteria} criteria, found {criteria_in_response}")
            validation_results['validation_passed'] = False
        
        # SAFEGUARD 3: Math Validator
        if 'final_validation' in parsed_response:
            final_val = parsed_response['final_validation']
            declared_final_score = float(final_val.get('final_score', 0))
            # Sum numerically over corrected entries using the helper
            calculated_sum = 0.0
            for v in corrected_scores.values():
                from .utils import get_criterion_score as _extract_score
                calculated_sum += _extract_score(v)
            
            if abs(declared_final_score - calculated_sum) > 0.1:  # Allow small floating point differences
                validation_results['issues_found'].append(f"Math mismatch: Declared {declared_final_score}, calculated {calculated_sum}")
                validation_results['corrections_made'].append(f"Using calculated sum: {calculated_sum}")
                
                # Recalculate percentage based on corrected sum
                # Try to get max_possible from score_ranges (dynamic), fallback to LLM's declared value
                max_possible = None
                try:
                    score_ranges = self._get_score_ranges()
                    if score_ranges:
                        max_possible = sum(score_ranges.values())
                        logger.debug(f"✅ Calculated max_possible from score_ranges: {max_possible}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not calculate max_possible from score_ranges: {e}")
                
                # Fallback to LLM's declared value if calculation failed
                if max_possible is None:
                    llm_declared = final_val.get('maximum_possible_score')
                    if llm_declared:
                        max_possible = float(llm_declared)
                        logger.debug(f"✅ Using LLM-declared max_possible: {max_possible}")
                    else:
                        logger.error("❌ Could not determine max_possible_score. Cannot recalculate percentage.")
                        max_possible = 0  # Prevent division by zero
                if max_possible > 0:
                    validation_results['validated_overall_score'] = (calculated_sum / max_possible) * 100
        
        # Safety criteria validation removed per user request
        
        # AUDIT TRAIL: Enhanced logging
        if validation_results['issues_found']:
            validation_results['validation_passed'] = False
            logger.warning(f"🚨 VALIDATION ISSUES FOUND: {len(validation_results['issues_found'])} issues")
            for issue in validation_results['issues_found']:
                logger.warning(f"   - {issue}")
        
        if validation_results['corrections_made']:
            logger.info(f"🔧 CORRECTIONS APPLIED: {len(validation_results['corrections_made'])} corrections")
            for correction in validation_results['corrections_made']:
                logger.info(f"   - {correction}")
        
        if validation_results['validation_passed']:
            logger.info("✅ VALIDATION PASSED: All scores within valid ranges")
        
        validation_results['audit_trail'].append({
            'timestamp': datetime.now().isoformat(),
            'original_score_count': len(detailed_scores),
            'corrected_score_count': len(corrected_scores),
            'original_overall': overall_score,
            'validated_overall': validation_results['validated_overall_score'],
            'issues_count': len(validation_results['issues_found']),
            'corrections_count': len(validation_results['corrections_made'])
        })
        
        return validation_results
    
    def _get_score_ranges(self) -> Dict[int, int]:
        """
        Dynamically extract maximum scores for each criterion from the prompt file.
        No hardcoded fallback - requires valid prompt file for accurate scoring.
        
        Returns:
            Dictionary mapping criterion_id -> max_score
            
        Raises:
            ValueError: If prompt_path is not available or parser fails to extract scores
        """
        # Require prompt_path to be available
        if not self._prompt_path or not self._prompt_path.exists():
            error_msg = f"Prompt path not available: {self._prompt_path}. Cannot extract score ranges without prompt file."
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        # Extract max scores from prompt parser (dynamic, maintainable)
        try:
            from .prompt_parser import get_parser
            parser = get_parser(self._prompt_path)
            max_scores = parser.get_max_scores_map()
            
            if not max_scores:
                error_msg = f"Failed to extract max scores from prompt file: {self._prompt_path.name}. No criteria found."
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            logger.debug(f"✅ Using dynamic max scores from prompt file: {len(max_scores)} criteria")
            return max_scores
            
        except ValueError:
            pass  # Ensure except block has body
            # Re-raise ValueError (already logged)
            raise
        except Exception as e:
            log_full_error(
                e,
                context={
                    'function': '_get_score_ranges',
                    'prompt_file': self._prompt_path.name if self._prompt_path else 'None'
                }
            )
            raise ValueError(error_msg) from e
    
    def _extract_criterion_id(self, parsed_response: Dict, criterion_name: str) -> int:
        """
        Extract criterion ID from parsed response or criterion name
        """
        # Try to find ID in the criteria array
        if 'criteria' in parsed_response:
            for criterion in parsed_response['criteria']:
                if isinstance(criterion, dict):
                    if criterion.get('criterion') == criterion_name:
                        return int(criterion.get('id', 0))
        
        # Fallback: extract from criterion name if it contains "criterion_X"
        if 'criterion_' in criterion_name:
            try:
                return int(criterion_name.split('criterion_')[1].split('_')[0])
            except:
                pass
        
        return 0  # Unknown criterion
    
    def _determine_expected_criteria_count(self, parsed_response: Dict) -> int:
        """
        Determine expected criteria count dynamically from prompt parser (no hardcoded assumptions)
        """
        # Calculate criteria count dynamically from score_ranges (most accurate)
        try:
            score_ranges = self._get_score_ranges()
            if score_ranges:
                criteria_count = len(score_ranges)
                logger.debug(f"✅ Calculated criteria count from score_ranges: {criteria_count}")
                return criteria_count
        except Exception as e:
            logger.warning(f"⚠️ Could not calculate criteria count from score_ranges: {e}")
        
        # Fallback: Try to count from criteria array in parsed_response
        if 'criteria' in parsed_response and isinstance(parsed_response['criteria'], list):
            criteria_count = len(parsed_response['criteria'])
            logger.debug(f"✅ Calculated criteria count from criteria array: {criteria_count}")
            return criteria_count
        
        # Last resort: Try to infer from max_possible_score if available
        if 'final_validation' in parsed_response:
            max_score = parsed_response['final_validation'].get('maximum_possible_score')
            if max_score:
                pass  # Ensure if block has body - FIRST indented line
                # Try to reverse-engineer count from max_score by checking score_ranges
                try:
                    score_ranges = self._get_score_ranges()
                    if score_ranges:
                        calculated_max = sum(score_ranges.values())
                        if abs(float(max_score) - calculated_max) < 0.1:  # Close match
                            return len(score_ranges)
                except Exception:
                    pass
        
        # If all else fails, raise error (no hardcoded fallback)
        error_msg = "Could not determine criteria count. Prompt file required for accurate count."
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)

    def get_usage_metrics(self) -> Dict[str, Any]:
        """Get current usage metrics"""
        return self._usage_metrics.get_summary()
    
    def get_prometheus_metrics(self) -> Dict[str, Any]:
        """Get current Prometheus metrics using public API"""
        try:
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST  # type: ignore
            import io
            
            # Get the raw Prometheus metrics using the default registry
            metrics_text = generate_latest().decode('utf-8')
            
            # Parse key metrics for structured response
            metrics_lines = metrics_text.strip().split('\n')
            parsed_metrics = {}
            
            for line in metrics_lines:
                if line.startswith('#') or not line.strip():
                    continue
                
                # Parse metric lines (format: metric_name{labels} value)
                if ' ' in line:
                    metric_part, value_part = line.rsplit(' ', 1)
                    try:
                        value = float(value_part)
                        
                        # Extract metric name (before first { or space)
                        metric_name = metric_part.split('{')[0].split(' ')[0]
                        
                        if metric_name not in parsed_metrics:
                            parsed_metrics[metric_name] = []
                        
                        parsed_metrics[metric_name].append({
                            "line": line,
                            "value": value,
                            "labels": metric_part
                        })
                    except ValueError:
                        continue
            
            # Get metrics URL from settings
            from .settings import settings
            metrics_url = settings.get_api_metrics_url()
            
            return {
                "raw_metrics": metrics_text,
                "parsed_metrics": parsed_metrics,
                "endpoint": metrics_url,
                "content_type": CONTENT_TYPE_LATEST,
                "total_metrics": len(parsed_metrics)
            }
            
        except Exception as e:
            log_full_error(e, context={'function': 'get_metrics'})
            # Get metrics URL from settings for error response
            from .settings import settings
            metrics_url = settings.get_api_metrics_url()
            return {
                "error": f"Failed to get Prometheus metrics: {str(e)}",
                "endpoint": metrics_url,
                "fallback": "Use direct Prometheus endpoint for metrics"
            }
    
    def reset_metrics(self):
        """Reset usage metrics (useful for testing)"""
        self._usage_metrics = UsageMetrics()
        logger.info("🔄 Usage metrics reset")
    
    def health_check(self) -> Dict[str, Any]:
        """Check engine health and status"""
        return {
            'status': 'healthy',
            'initialized': self._initialized,
            'llm_loaded': self._llm is not None,
            'prompt_loaded': self._prompt_template is not None,
            'usage_metrics': self.get_usage_metrics(),
            'timestamp': datetime.now().isoformat()
        }

# Global engine instance
evaluation_engine = EvaluationEngine()

# Convenience functions for backward compatibility
def evaluate_llm_output(summary: str, recommendation: str) -> Dict[str, Any]:
    """Backward compatible function for single case evaluation"""
    return evaluation_engine.evaluate_single_case(summary, recommendation)

def get_evaluation_metrics() -> Dict[str, Any]:
    """Get current evaluation metrics"""
    return evaluation_engine.get_usage_metrics()

def get_prometheus_metrics() -> Dict[str, Any]:
    """Get current Prometheus metrics"""
    return evaluation_engine.get_prometheus_metrics()

def reset_evaluation_metrics():
    """Reset evaluation metrics"""
    evaluation_engine.reset_metrics()
