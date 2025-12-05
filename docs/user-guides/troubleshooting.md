# Troubleshooting Guide

Common issues and solutions for the MedBench Automation Testing Tool.

## Quick Diagnostics

### Check System Status

```bash
# Check all services
docker-compose ps

# Check API health
curl http://localhost:8000/api/health

# Check service logs
docker-compose logs --tail=50
```

## Common Issues

### API Not Starting

**Symptoms:**
- API container exits immediately
- Health check fails
- Cannot access API docs

**Solutions:**

```bash
# Check API logs
docker-compose logs api

# Common causes:
# 1. Missing environment variables
docker-compose exec api env | grep OPENAI

# 2. Database connection issues
docker-compose logs postgres

# 3. Port conflicts
netstat -an | grep 8000

# Restart API
docker-compose restart api
```

### Database Connection Errors

**Symptoms:**
- "Failed to connect to database"
- Database errors in logs
- Jobs not saving

**Solutions:**

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres

# Verify credentials
docker-compose exec postgres psql -U medbench -d jarvismd -c "SELECT 1"

# Reset database password (if needed)
docker-compose exec postgres psql -U medbench -d jarvismd -c "ALTER USER medbench WITH PASSWORD 'medbench_secure_password_change_in_production';"
```

### Celery Workers Not Processing

**Symptoms:**
- Jobs stuck in "running" status
- No progress updates
- Tasks queued but not executing

**Solutions:**

```bash
# Check worker status
docker-compose logs celery-worker

# Check Redis connection
docker-compose exec redis redis-cli ping

# Check task queue
docker-compose exec redis redis-cli LLEN celery

# Restart worker
docker-compose restart celery-worker

# Check worker concurrency
docker-compose exec celery-worker ps aux | grep celery
```

### Evaluations Failing

**Symptoms:**
- Cases showing 0.0 score
- Error messages in results
- Jobs completing with failures

**Solutions:**

```bash
# Check OpenAI API key
docker-compose exec api env | grep OPENAI_API_KEY

# Verify API key is valid
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check API credits
# Visit https://platform.openai.com/usage

# Review error logs
docker-compose logs celery-worker | grep -i error

# Check traces in Grafana
# Look for error spans with error attributes
```

### Frontend Not Loading

**Symptoms:**
- Blank page
- Network errors
- Cannot connect to API

**Solutions:**

```bash
# Check frontend is running
cd frontend && npm run dev

# Check API is accessible
curl http://localhost:8000/api/health

# Check CORS configuration
# Verify CORS_ORIGINS includes frontend URL

# Check browser console for errors
# Open DevTools (F12) and check Console tab
```

### Medical Cases Not Found

**Symptoms:**
- Case count shows 0
- "No cases available" message
- Evaluations fail to start

**Solutions:**

```bash
# Verify cases directory exists
ls -la jarvismd/data/medical_cases/drstrange/

# Check volume mount
docker-compose exec api ls -la /app/jarvismd/data/medical_cases/

# Verify case structure
# Each case should have:
# - summary.txt
# - recommendation.txt
# - (optional) annotated_transcription.txt

# Check case count API
curl http://localhost:8000/api/cases/count
```

### Traces Not Appearing

**Symptoms:**
- "View Trace" shows 404
- No traces in Grafana
- Trace ID is null

**Solutions:**

```bash
# Check Tempo is running
docker-compose ps tempo

# Check OpenTelemetry Collector
docker-compose logs otel-collector

# Verify trace export
docker-compose logs api | grep -i trace

# Check Tempo retention
# Traces may expire after retention period

# Verify Grafana datasource
# Check Tempo datasource is configured in Grafana
```

### Low Performance

**Symptoms:**
- Slow evaluations
- High CPU/memory usage
- Timeouts

**Solutions:**

```bash
# Check system resources
docker stats

# Increase worker concurrency
# Edit docker-compose.yml:
# command: celery ... --concurrency=8

# Check API rate limits
# Monitor OpenAI API usage

# Optimize batch size
# Process smaller batches if memory constrained
```

## Error Messages

### "IndentationError"

**Cause:** Python syntax error in code

**Solution:**
```bash
# Rebuild container with latest code
docker-compose build --no-cache api
docker-compose restart api
```

### "Failed to connect to database"

**Cause:** Database connection issue

**Solution:**
```bash
# Check database is running
docker-compose ps postgres

# Verify credentials match
# Check .env file matches docker-compose.yml

# Reset database password if needed
```

### "No trace_id found"

**Cause:** OpenTelemetry not initialized

**Solution:**
```bash
# Check OpenTelemetry setup
docker-compose logs api | grep -i opentelemetry

# Verify OTEL_EXPORTER_OTLP_ENDPOINT is set
docker-compose exec api env | grep OTEL

# Restart services
docker-compose restart api celery-worker
```

### "Content moderation triggered"

**Cause:** OpenAI content filter blocked response

**Solution:**
- Review case content
- Check for sensitive information
- Modify case data if needed
- Case will be saved with 0.0 score

### "Parsing failed - No valid JSON"

**Cause:** LLM response not in expected format

**Solution:**
- Check trace in Grafana
- Review raw LLM response
- Verify prompt file is correct
- Case will be saved with 0.0 score

## Debugging Tools

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f celery-worker
docker-compose logs -f postgres

# Last 100 lines
docker-compose logs --tail=100 api
```

### Check Database

```bash
# Connect to database
docker-compose exec postgres psql -U medbench -d jarvismd

# Check tables
\dt

# Check recent jobs
SELECT id, status, total_cases, processed_cases FROM test_jobs ORDER BY start_time DESC LIMIT 5;

# Check results
SELECT case_id, total_score, trace_id FROM evaluation_results ORDER BY created_at DESC LIMIT 5;
```

### Check Redis

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Check queue length
LLEN celery

# View queued tasks
LRANGE celery 0 -1

# Clear queue (if needed)
FLUSHDB
```

### Monitor Metrics

```bash
# Prometheus metrics
curl http://localhost:9090/api/v1/query?query=evaluations_total

# API metrics
curl http://localhost:8007/metrics

# Worker metrics
curl http://localhost:8006/metrics
```

## Getting Help

### Check Documentation

- [Installation Guide](../getting-started/installation.md)
- [Configuration Guide](../getting-started/configuration.md)
- [User Guides](../user-guides/)

### Review Logs

Always check logs first:
```bash
docker-compose logs --tail=100
```

### Check Traces

Use distributed traces in Grafana:
1. Get trace_id from results
2. Open Grafana
3. Navigate to trace
4. Review spans for errors

### Common Solutions

1. **Restart Services**: Often fixes transient issues
   ```bash
   docker-compose restart
   ```

2. **Rebuild Containers**: Fixes code-related issues
   ```bash
   docker-compose build --no-cache
   docker-compose up -d
   ```

3. **Check Environment**: Verify all required variables
   ```bash
   docker-compose config
   ```

4. **Verify Network**: Ensure services can communicate
   ```bash
   docker-compose exec api ping postgres
   docker-compose exec api ping redis
   ```

## Prevention

### Best Practices

1. **Regular Monitoring**: Check system health regularly
2. **Resource Management**: Monitor CPU/memory usage
3. **Error Tracking**: Review error logs proactively
4. **Backup Data**: Regular database backups
5. **Update Dependencies**: Keep packages updated

### Health Checks

```bash
# Create health check script
#!/bin/bash
curl -f http://localhost:8000/api/health || echo "API unhealthy"
docker-compose exec postgres pg_isready || echo "Database unhealthy"
docker-compose exec redis redis-cli ping || echo "Redis unhealthy"
```

## Next Steps

- [Installation Guide](../getting-started/installation.md)
- [Configuration Guide](../getting-started/configuration.md)
- [Architecture Overview](../architecture/)

