# Running Evaluations

Complete guide to running medical case evaluations in the MedBench Automation Testing Tool.

## Overview

Evaluations can be run through:
- **Web UI**: User-friendly interface for starting and monitoring evaluations
- **API**: Programmatic access for automation and integration

## Using the Web UI

### Starting an Evaluation

1. **Navigate to Test Runner**
   - Open the application (http://localhost:5173)
   - Click "Test Runner" in the sidebar

2. **Select Configuration**
   - **Benchmark**: Choose from available benchmarks (e.g., `appraise_v2`)
   - **Number of Cases**: Enter the number of cases to evaluate
     - Start with small numbers (1-5) for testing
     - System will automatically count available cases
   - **Model**: Uses default model from configuration (usually `gpt-4o`)

3. **Start Evaluation**
   - Click "Start Evaluation" button
   - Job ID will be generated and displayed
   - Status will show "running"

### Monitoring Progress

**Dashboard View:**
- Real-time job status
- Progress percentage
- Cases processed / total cases
- Estimated completion time

**Job Details:**
- Click on job in Results page
- View detailed progress
- See individual case status

### Canceling an Evaluation

- Click "Cancel" button on active job
- Job status changes to "cancelled"
- Currently processing cases complete
- Remaining cases are skipped

## Using the API

### Start Evaluation Endpoint

```bash
POST /api/test/start
Content-Type: application/json

{
  "benchmark_name": "appraise_v2",
  "num_cases": 10
}
```

**Response:**
```json
{
  "job_id": "abc123-def456-...",
  "status": "running",
  "total_cases": 10,
  "benchmark": "appraise_v2",
  "model": "gpt-4o",
  "start_time": "2025-11-26T10:00:00Z"
}
```

### Check Status

```bash
GET /api/test/{job_id}/status
```

**Response:**
```json
{
  "job_id": "abc123...",
  "status": "running",
  "total_cases": 10,
  "processed_cases": 7,
  "progress_percentage": 70.0,
  "start_time": "2025-11-26T10:00:00Z",
  "estimated_completion": "2025-11-26T10:05:00Z"
}
```

### Get Results

```bash
GET /api/test/{job_id}/results
```

Returns complete results when job is completed.

## Evaluation Process

### Step-by-Step Flow

1. **Job Creation**
   - TestJob record created in database
   - Status set to "running"
   - Start time recorded

2. **Case Loading**
   - System scans medical cases directory
   - Loads case files (summary.txt, recommendation.txt)
   - Validates case structure

3. **Batch Processing**
   - Cases queued to Celery workers
   - Workers process cases concurrently
   - Progress tracked in real-time

4. **Evaluation**
   - Each case evaluated by LLM
   - Scores calculated for 24 criteria
   - Complexity assessed
   - Results stored in database

5. **Completion**
   - Job status updated to "completed"
   - End time recorded
   - Summary statistics calculated

### Concurrency

- **Default**: 4 Celery workers
- **Configurable**: Adjust in `docker-compose.yml`
- **Throughput**: ~20 cases/minute (4 workers)

## Batch Processing Details

### How Cases are Processed

1. **Queue Distribution**
   - Cases distributed across available workers
   - Load balancing handled by Celery
   - Failed cases retried automatically

2. **Error Handling**
   - Failed cases saved with 0.0 score
   - Error details stored in evaluation_text
   - Job continues processing other cases
   - Failed cases automatically flagged

3. **Progress Tracking**
   - Real-time updates via database
   - Progress percentage calculated
   - Estimated completion time

### Retry Logic

- **Max Retries**: 2 attempts per case
- **Retry Delay**: Exponential backoff
- **Permanent Failures**: Saved with error details

## Performance Considerations

### Optimization Tips

1. **Batch Size**
   - Larger batches = better throughput
   - Balance with memory usage
   - Recommended: 10-50 cases per batch

2. **Worker Scaling**
   - More workers = faster processing
   - Monitor CPU/memory usage
   - Default 4 workers is usually sufficient

3. **API Rate Limits**
   - OpenAI has rate limits
   - System handles rate limiting automatically
   - Consider API tier for large batches

### Resource Usage

- **CPU**: Moderate (LLM API calls are I/O bound)
- **Memory**: ~500MB per worker
- **Network**: Depends on case size and API response

## Monitoring Evaluations

### Real-Time Monitoring

**Dashboard:**
- Active jobs count
- Processing rate
- Success/failure rates

**Grafana:**
- Evaluation metrics
- Processing times
- Token usage
- Error rates

**Flower (Celery):**
- Task queue status
- Worker status
- Task execution times

### Logs

```bash
# View API logs
docker-compose logs -f api

# View Celery worker logs
docker-compose logs -f celery-worker

# View all logs
docker-compose logs -f
```

## Best Practices

1. **Start Small**: Test with 1-3 cases first
2. **Monitor Resources**: Watch system metrics
3. **Check Logs**: Monitor for errors
4. **Validate Results**: Review scores make sense
5. **Use Traces**: Debug issues with distributed traces

## Troubleshooting

### Evaluation Not Starting

- Check Celery worker is running
- Verify Redis connection
- Check for errors in logs
- Verify medical cases exist

### Slow Processing

- Check API rate limits
- Monitor worker count
- Review network latency
- Check system resources

### Failed Cases

- Review error logs
- Check OpenAI API status
- Verify API key is valid
- Review trace in Grafana

## Next Steps

- [Viewing Results](viewing-results.md)
- [Understanding Scores](understanding-scores.md)
- [Troubleshooting Guide](troubleshooting.md)

