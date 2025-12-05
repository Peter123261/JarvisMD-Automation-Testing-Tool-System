# Running Your First Evaluation

This guide will walk you through running your first medical case evaluation.

## Prerequisites

- System installed and running (see [Installation](installation.md))
- Configuration completed (see [Configuration](configuration.md))
- Medical cases available in `jarvismd/data/medical_cases/`

## Quick Start

### Step 1: Verify System is Ready

```bash
# Check all services are running
docker-compose ps

# Verify API is healthy
curl http://localhost:8000/api/health

# Check available cases
curl http://localhost:8000/api/cases/count
```

### Step 2: Start the Frontend

**Option A: Using Docker (if configured)**
```bash
# Frontend should be accessible if included in docker-compose
```

**Option B: Local Development**
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

### Step 3: Run an Evaluation via UI

1. **Navigate to Test Runner**
   - Open http://localhost:5173
   - Click "Test Runner" in the sidebar

2. **Configure Evaluation**
   - Select benchmark: `appraise_v2` (or available benchmark)
   - Enter number of cases: Start with 1-3 cases for testing
   - Click "Start Evaluation"

3. **Monitor Progress**
   - Watch the Dashboard for real-time updates
   - Job status will show "running" → "completed"
   - Progress bar shows completion percentage

4. **View Results**
   - Go to "Results" page
   - Click "View Cases" for your job
   - See detailed scores and criteria breakdown

## Running via API

### Using cURL

```bash
# Start an evaluation
curl -X POST "http://localhost:8000/api/test/start" \
  -H "Content-Type: application/json" \
  -d '{
    "benchmark_name": "appraise_v2",
    "num_cases": 3
  }'

# Response:
# {
#   "job_id": "abc123...",
#   "status": "running",
#   "total_cases": 3,
#   ...
# }
```

### Check Job Status

```bash
# Replace JOB_ID with the job_id from previous response
curl "http://localhost:8000/api/test/JOB_ID/status"
```

### Get Results

```bash
# Get results when job is completed
curl "http://localhost:8000/api/test/JOB_ID/results"
```

## Understanding the Results

### Result Structure

Each evaluation result contains:

- **Overall Score**: Percentage score (0-100%)
- **Criteria Scores**: Individual scores for each of 24 criteria
- **Complexity Level**: Low/Moderate/High/Very High
- **Processing Time**: Time taken to evaluate
- **Token Usage**: Input/output/total tokens
- **Trace ID**: Link to distributed trace in Grafana

### Score Interpretation

- **≥ 97/129 (75%)**: Excellent performance
- **65-96/129 (50-74%)**: Needs improvement
- **< 65/129 (50%)**: Poor performance
- **< 75%**: Automatically flagged for review

### Viewing Traces

1. Click "View Trace" button in Results page
2. Opens Grafana with the trace
3. Explore spans to see:
   - LLM invocation details
   - Parsing steps
   - Error information (if any)

## Example Workflow

### Complete Example

```bash
# 1. Start evaluation
JOB_ID=$(curl -s -X POST "http://localhost:8000/api/test/start" \
  -H "Content-Type: application/json" \
  -d '{"benchmark_name": "appraise_v2", "num_cases": 2}' \
  | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# 2. Monitor status
while true; do
  STATUS=$(curl -s "http://localhost:8000/api/test/$JOB_ID/status" | jq -r '.status')
  echo "Status: $STATUS"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "error" ]; then
    break
  fi
  
  sleep 5
done

# 3. Get results
curl "http://localhost:8000/api/test/$JOB_ID/results" | jq '.'
```

## Troubleshooting

### Evaluation Not Starting

```bash
# Check Celery worker is running
docker-compose logs celery-worker

# Check for errors
docker-compose logs api | grep -i error
```

### Cases Not Found

```bash
# Verify medical cases directory
ls -la jarvismd/data/medical_cases/drstrange/

# Check case count API
curl http://localhost:8000/api/cases/count
```

### Job Stuck in "Running"

```bash
# Check worker logs
docker-compose logs -f celery-worker

# Check Redis queue
docker-compose exec redis redis-cli LLEN celery

# Restart worker if needed
docker-compose restart celery-worker
```

### Low Scores or Failures

- Check OpenAI API key is valid
- Verify API credits are available
- Review error logs in Grafana traces
- Check evaluation_text field for error details

## Best Practices

1. **Start Small**: Test with 1-3 cases first
2. **Monitor Resources**: Watch CPU/memory usage
3. **Check Logs**: Monitor for errors or warnings
4. **Review Traces**: Use distributed tracing for debugging
5. **Validate Results**: Verify scores make sense

## Next Steps

- [Learn about viewing results](../user-guides/viewing-results.md)
- [Understand scoring system](../user-guides/understanding-scores.md)
- [Explore the architecture](../architecture/)

