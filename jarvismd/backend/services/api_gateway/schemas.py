"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Request Models
class EvaluationRequest(BaseModel):
    benchmark_name: str = Field(..., description="Evaluation benchmark to use (system will automatically load {benchmark_name}.txt from prompts directory)")
    num_cases: int = Field(..., ge=1, le=1000, description="Number of cases to evaluate")

class SingleEvaluationRequest(BaseModel):
    summary: str = Field(..., description="Medical case summary")
    recommendation: str = Field(..., description="AI recommendation to evaluate")

# Response Models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    database: str
    total_test_jobs: int
    openai_configured: bool

class CaseCountResponse(BaseModel):
    total_cases: int
    doctors: Dict[str, int]
    scan_time: str
    data_directory: str

class BenchmarkInfo(BaseModel):
    id: str
    name: str
    description: str
    criteria_count: int
    version: str
    prompt_file: str

class BenchmarksResponse(BaseModel):
    benchmarks: List[BenchmarkInfo]

class EvaluationJobResponse(BaseModel):
    job_id: str
    status: str
    total_cases: int
    benchmark: str
    model: str
    start_time: str

class ProgressInfo(BaseModel):
    processed: int
    total: int
    percentage: float

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: ProgressInfo
    benchmark: str
    model: str
    start_time: str
    end_time: Optional[str] = None
    error_message: Optional[str] = None

class ResultSummary(BaseModel):
    total_evaluations: int
    average_score: float
    benchmark: str
    model: str
    completion_time: Optional[str] = None
    cases_flagged_for_review: int = 0  # NEW
    review_threshold: float = 75.0    # NEW

class DetailedResult(BaseModel):
    case_id: str
    doctor_name: str
    case_name: str
    total_score: float
    criteria_scores: Dict[str, Any]
    processing_time: float
    created_at: str
    complexity_level: Optional[str] = None  # Low/Moderate/High
    flagged_for_review: bool = False      # NEW
    review_priority: str = "none"         # NEW (high/medium/none)
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    evaluation_text: Optional[str] = None  # Full OpenAI response
    trace_id: Optional[str] = None  # OpenTelemetry trace ID for distributed tracing

class JobResultsResponse(BaseModel):
    job_id: str
    summary: ResultSummary
    detailed_results: List[DetailedResult]
    criteria_schema: Optional[List[Dict[str, Any]]] = None  # Full criteria schema with id, name, description, max_score, is_safety
    criterion_max_scores: Optional[Dict[int, int]] = None  # Map of criterion_id -> max_score (deprecated, use criteria_schema)
    criterion_name_to_max_score: Optional[Dict[str, int]] = None  # Map of criterion_name -> max_score (deprecated, use criteria_schema)

# Error Response Models
class ErrorResponse(BaseModel):
    detail: str
    timestamp: str
    error_type: Optional[str] = None

# Root Response Model
class RootResponse(BaseModel):
    message: str
    version: str
    docs: str
    status: str
    database: str
    timestamp: str



