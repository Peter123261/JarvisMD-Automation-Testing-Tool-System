# API Endpoints

Complete reference for all API endpoints in the MedBench Automation Testing Tool.

## Base URL

```
http://localhost:8000/api
```

## Authentication

Currently, the API does not require authentication. In production, implement API keys or OAuth2.

## Endpoints

### Health & Status

#### GET /health

Basic health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-26T10:00:00Z",
  "service": "JarvisMD Automation Testing Tool",
  "version": "1.0.0"
}
```

#### GET /health/detailed

Detailed health check with system metrics.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-26T10:00:00Z",
  "configuration": {
    "openai_configured": true,
    "database_url": true,
    "environment": "development"
  },
  "system_metrics": {
    "memory_usage_percent": 45.2,
    "cpu_usage_percent": 12.5,
    "disk_usage_percent": 32.1
  },
  "services": {
    "api_gateway": "running",
    "evaluation_service": "pending",
    "analysis_service": "pending",
    "reporting_service": "pending"
  }
}
```

#### GET /health/database

Health check with database verification.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-26T10:00:00Z",
  "database": "connected",
  "total_test_jobs": 15,
  "openai_configured": true
}
```

### Evaluation Endpoints

#### POST /test/start

Start a new evaluation job.

**Request:**
```json
{
  "benchmark_name": "appraise_v2",
  "num_cases": 10
}
```

**Response:**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "running",
  "total_cases": 10,
  "benchmark": "appraise_v2",
  "model": "gpt-4o",
  "start_time": "2025-11-26T10:00:00Z"
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid request (benchmark not found, invalid case count)
- `500`: Server error

#### GET /test/{job_id}/status

Get the status of an evaluation job.

**Response:**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "running",
  "total_cases": 10,
  "processed_cases": 7,
  "progress_percentage": 70.0,
  "start_time": "2025-11-26T10:00:00Z",
  "estimated_completion": "2025-11-26T10:05:00Z"
}
```

**Status Values:**
- `pending`: Job created but not started
- `running`: Job in progress
- `completed`: Job finished successfully
- `error`: Job failed
- `cancelled`: Job was cancelled

#### GET /test/{job_id}/results

Get complete results for a completed job.

**Response:**
```json
{
  "job_id": "abc123-def456-ghi789",
  "summary": {
    "total_evaluations": 10,
    "successful_evaluations": 9,
    "failed_evaluations": 1,
    "average_score": 87.5,
    "cases_flagged_for_review": 2,
    "p95_duration_seconds": 3.2,
    "average_duration_seconds": 2.8
  },
  "detailed_results": [
    {
      "case_id": "Day-1-Consult-1-Diarrhea",
      "total_score": 89.1,
      "criteria_scores": {
        "1": 7,
        "2": 3,
        ...
      },
      "processing_time": 2.5,
      "trace_id": "abc123...",
      "flagged_for_review": false
    }
  ],
  "criteria_schema": [
    {
      "id": 1,
      "name": "Does the model's recommendation focus on...",
      "description": "Full criterion text",
      "max_score": 8,
      "is_safety": false
    }
  ]
}
```

#### POST /test/{job_id}/cancel

Cancel a running evaluation job.

**Response:**
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "cancelled",
  "message": "Job cancelled successfully"
}
```

### Results Endpoints

#### GET /results/summary

Get summary statistics of evaluation results.

**Query Parameters:**
- `job_id` (optional): Filter by specific job
- `start_date` (optional): Filter from date (YYYY-MM-DD)
- `end_date` (optional): Filter to date (YYYY-MM-DD)
- `benchmark` (optional): Filter by benchmark
- `include_failed` (optional): Include failed evaluations (default: false)

**Response:**
```json
{
  "total_evaluations": 100,
  "successful_evaluations": 95,
  "failed_evaluations": 5,
  "average_score": 85.2,
  "cases_flagged_for_review": 12,
  "p95_duration_seconds": 3.5,
  "average_duration_seconds": 2.9,
  "review_threshold": 75.0
}
```

#### GET /results/jobs/recent

Get list of recent evaluation jobs.

**Query Parameters:**
- `limit` (optional): Number of jobs to return (default: 10, max: 50)
- `benchmark` (optional): Filter by benchmark

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "abc123...",
      "benchmark": "appraise_v2",
      "total_cases": 10,
      "processed_cases": 10,
      "average_score": 87.5,
      "status": "completed",
      "start_time": "2025-11-26T10:00:00Z",
      "end_time": "2025-11-26T10:05:00Z"
    }
  ]
}
```

#### GET /results/trace/{trace_id}

Get trace viewing URLs for a trace ID.

**Response:**
```json
{
  "trace_id": "abc123def456...",
  "grafana_url": "http://localhost:3000/explore?...",
  "tempo_url": "http://localhost:3200/api/traces/abc123...",
  "jaeger_url": "http://localhost:16686/trace/abc123..."
}
```

### Case Management

#### GET /cases/count

Get count of available medical cases.

**Response:**
```json
{
  "total_cases": 19,
  "doctors": {
    "drstrange": 19
  },
  "scan_time": "2025-11-26T10:00:00Z",
  "data_directory": "/app/jarvismd/data/medical_cases"
}
```

### Benchmark Management

#### GET /benchmarks

Get list of available evaluation benchmarks.

**Response:**
```json
{
  "benchmarks": [
    {
      "id": "appraise_v2",
      "name": "Appraise V2 Evaluation",
      "description": "Evaluation benchmark using Appraise_v2.txt",
      "criteria_count": 24,
      "version": "1.0",
      "prompt_file": "Appraise_v2.txt"
    }
  ]
}
```

## Error Responses

### Standard Error Format

```json
{
  "detail": "Error message description",
  "timestamp": "2025-11-26T10:00:00Z",
  "error_type": "ValidationError"
}
```

### Status Codes

- `200`: Success
- `400`: Bad Request (validation error)
- `404`: Not Found (resource doesn't exist)
- `500`: Internal Server Error

## Rate Limiting

Currently no rate limiting implemented. Consider adding in production.

## Pagination

Results endpoints support pagination via query parameters:
- `limit`: Number of results (default: 50, max: 100)
- `offset`: Skip N results (default: 0)

## Examples

### Start Evaluation

```bash
curl -X POST "http://localhost:8000/api/test/start" \
  -H "Content-Type: application/json" \
  -d '{
    "benchmark_name": "appraise_v2",
    "num_cases": 5
  }'
```

### Check Status

```bash
curl "http://localhost:8000/api/test/abc123-def456-ghi789/status"
```

### Get Results

```bash
curl "http://localhost:8000/api/test/abc123-def456-ghi789/results"
```

### Get Summary

```bash
curl "http://localhost:8000/api/results/summary?job_id=abc123-def456-ghi789"
```

## Interactive Documentation

Swagger UI available at:
- http://localhost:8000/api/docs

ReDoc available at:
- http://localhost:8000/api/redoc

## Next Steps

- [Authentication](authentication.md)
- [Examples](examples.md)

