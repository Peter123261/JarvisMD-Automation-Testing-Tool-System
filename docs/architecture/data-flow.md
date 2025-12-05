# Data Flow

How data moves through the MedBench Automation Testing Tool system.

## Evaluation Request Flow

### 1. User Initiates Evaluation

```
User (UI) → TestRunner Component
  ↓
POST /api/test/start
  {
    "benchmark_name": "appraise_v2",
    "num_cases": 10
  }
```

### 2. API Gateway Processing

```
API Gateway (FastAPI)
  ↓
1. Validate request (Pydantic)
2. Check benchmark exists
3. Count available cases
4. Create TestJob record
   - id: UUID
   - status: "running"
   - total_cases: 10
   - benchmark: "appraise_v2"
5. Queue Celery task
6. Return job_id
```

### 3. Task Queue Distribution

```
Celery Task Queue
  ↓
Task: run_batch_evaluation
  - job_id: "abc123..."
  - benchmark: "appraise_v2"
  - num_cases: 10
  ↓
Redis Queue: "celery"
  ↓
Worker picks up task
```

### 4. Case Loading

```
Celery Worker
  ↓
1. Load medical cases from filesystem
   - Scan: jarvismd/data/medical_cases/drstrange/
   - Load: summary.txt, recommendation.txt
2. Parse case data
3. Create case list
```

### 5. Batch Processing

```
For each case:
  ↓
Worker → Evaluation Engine
  ↓
1. Load prompt template (cached)
2. Initialize LLM (singleton)
3. Create OpenTelemetry span
4. Invoke LLM with case data
5. Parse JSON response
6. Calculate scores
7. Assess complexity
8. Extract trace_id
9. Return result
  ↓
Worker → Database
  ↓
Save EvaluationResult:
  - case_id
  - total_score
  - criteria_scores (JSON)
  - trace_id
  - processing_time
  - tokens
```

### 6. Progress Updates

```
Worker → Database
  ↓
Update TestJob:
  - processed_cases: +1
  - status: "running"
  ↓
Frontend polls:
  GET /api/test/{job_id}/status
  ↓
Returns progress percentage
```

### 7. Completion

```
All cases processed
  ↓
Worker → Database
  ↓
Update TestJob:
  - status: "completed"
  - end_time: timestamp
  - processed_cases: 10
  ↓
Frontend detects completion
  ↓
Display results
```

## Trace Flow

### Span Creation

```
Evaluation Request
  ↓
API Gateway creates span:
  - name: "POST /api/test/start"
  - trace_id: generated
  ↓
Celery Task creates span:
  - name: "run_batch_evaluation"
  - parent: API span
  ↓
Each case creates span:
  - name: "evaluate_single_case"
  - parent: batch span
  ↓
LLM invocation creates span:
  - name: "llm_invoke"
  - parent: case span
  ↓
Parsing creates span:
  - name: "parse_evaluation_result"
  - parent: case span
```

### Trace Export

```
All Services
  ↓
OpenTelemetry SDK
  ↓
Batch Span Processor
  - Collects spans
  - Batches (10 spans or 100ms)
  ↓
OTLP Exporter
  ↓
OpenTelemetry Collector
  ↓
Tempo (Trace Storage)
```

### Trace Query

```
User clicks "View Trace"
  ↓
Frontend → API
  GET /api/results/trace/{trace_id}
  ↓
API returns Grafana URL
  ↓
Frontend opens Grafana
  ↓
Grafana queries Tempo
  ↓
Display trace visualization
```

## Metrics Flow

### Metric Collection

```
Evaluation Engine
  ↓
Prometheus Client
  - Counter: evaluations_total
  - Histogram: evaluation_duration_seconds
  - Gauge: evaluation_success_rate
  ↓
HTTP Endpoint: /metrics
  ↓
Prometheus Scraper
  - Scrapes every 10s
  - Stores in time-series DB
```

### Metric Query

```
Grafana Dashboard
  ↓
PromQL Query
  - rate(evaluations_total[5m])
  - histogram_quantile(0.95, evaluation_duration_seconds)
  ↓
Prometheus
  ↓
Returns metric values
  ↓
Grafana visualizes
```

## Error Flow

### Error Detection

```
Evaluation fails
  ↓
Exception caught
  ↓
Error Logger
  - Logs full traceback
  - Includes context
  - Sets log level
  ↓
OpenTelemetry Span
  - Status: ERROR
  - Attributes: error=true, error.type, error.message
  - record_exception()
```

### Error Storage

```
Failed Case
  ↓
EvaluationResult saved:
  - total_score: 0.0
  - error details in evaluation_text
  - trace_id: for debugging
  - flagged_for_review: true
  ↓
AlertQueue entry created:
  - alert_type: "low_score"
  - severity: "high"
```

## Database Flow

### Write Operations

```
Create TestJob
  ↓
INSERT INTO test_jobs
  ↓
Commit transaction
  ↓
Return job_id
```

```
Save EvaluationResult
  ↓
INSERT INTO evaluation_results
  ↓
If score < 75:
  INSERT INTO alert_queue
  ↓
Commit transaction
```

### Read Operations

```
Get Results Summary
  ↓
SELECT FROM evaluation_results
  WHERE test_job_id = ?
  ↓
Aggregate:
  - COUNT(*)
  - AVG(total_score)
  - COUNT(WHERE total_score < 75)
  ↓
Return summary
```

## Cache Flow

### LLM Instance Cache

```
First Evaluation
  ↓
Evaluation Engine
  ↓
Create LLM instance
  ↓
Store in _instance._llm
  ↓
Subsequent Evaluations
  ↓
Reuse cached instance
```

### Prompt Template Cache

```
First Evaluation
  ↓
Load prompt file
  ↓
Parse template
  ↓
Store in _instance._prompt_template
  ↓
Subsequent Evaluations
  ↓
Reuse cached template
```

## Next Steps

- [System Overview](system-overview.md)
- [Components](components.md)
- [Monitoring Stack](monitoring-stack.md)

