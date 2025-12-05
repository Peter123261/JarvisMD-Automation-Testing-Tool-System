# Monitoring Setup

Complete guide to setting up and using the monitoring stack.

## Monitoring Stack Overview

The system includes:
- **Prometheus**: Metrics collection
- **Grafana**: Visualization
- **Tempo**: Distributed tracing
- **Alertmanager**: Alert routing
- **OpenTelemetry**: Instrumentation

## Accessing Monitoring Tools

### Grafana

- **URL**: http://localhost:3000
- **Default Credentials**: admin/admin
- **Change on first login**

### Prometheus

- **URL**: http://localhost:9090
- **No authentication** (add in production)

### Alertmanager

- **URL**: http://localhost:9093
- **No authentication** (add in production)

### Tempo

- **API**: http://localhost:3200
- **Access via Grafana** (recommended)

## Grafana Dashboards

### Pre-configured Dashboards

Located in `monitoring/grafana/dashboards/`:

1. **System Overview**
   - Service health
   - Container metrics
   - Resource usage

2. **Medical Evaluation Analytics**
   - Evaluation metrics
   - Success/failure rates
   - Processing times
   - Token usage
   - Cost estimates

3. **Container Overview**
   - Per-container metrics
   - CPU/Memory usage
   - Network I/O

### Accessing Dashboards

1. Log into Grafana
2. Navigate to Dashboards
3. Select dashboard from list
4. Customize as needed

## Prometheus Queries

### Common Queries

**Total Evaluations:**
```promql
evaluations_total
```

**Success Rate:**
```promql
rate(evaluations_success_total[5m]) / rate(evaluations_total[5m]) * 100
```

**P95 Processing Time:**
```promql
histogram_quantile(0.95, evaluation_duration_seconds_bucket)
```

**Token Usage:**
```promql
rate(tokens_total[5m])
```

**Flagged Cases:**
```promql
rate(cases_flagged_total[5m])
```

## Alert Configuration

### Alert Rules

Located in `monitoring/alert_rules.yml`

**Example Alerts:**
- Low success rate (< 80%)
- High failure rate (> 20%)
- High CPU usage (> 90%)
- High memory usage (> 90%)

### Alertmanager Configuration

Located in `monitoring/alertmanager.yml`

**Configure:**
- Notification channels (email, Slack)
- Routing rules
- Grouping and deduplication

## Distributed Tracing

### Viewing Traces

1. Get trace_id from evaluation result
2. Open Grafana → Explore
3. Select Tempo datasource
4. Enter trace_id or use TraceQL

### TraceQL Queries

```
# Find traces with errors
{status=error}

# Find slow evaluations
{duration>5s}

# Find specific job
{job_id="abc123..."}
```

### Trace Attributes

Common attributes to check:
- `error`: true/false
- `error.type`: Error type
- `error.message`: Error message
- `evaluation.duration_seconds`: Processing time
- `llm.model`: Model used
- `result.flagged`: Whether case is flagged

## Metrics Endpoints

### API Metrics

- **URL**: http://localhost:8007/metrics
- **Format**: Prometheus text format
- **Scraped**: Every 10 seconds

### Worker Metrics

- **URL**: http://localhost:8006/metrics
- **Format**: Prometheus text format
- **Scraped**: Every 10 seconds

## Custom Dashboards

### Creating Dashboards

1. Log into Grafana
2. Create → Dashboard
3. Add panels
4. Configure queries
5. Save dashboard

### Dashboard Variables

Use variables for filtering:
- `$job_id`: Filter by job
- `$benchmark`: Filter by benchmark
- `$time_range`: Time range selector

## Alerting

### Setting Up Alerts

1. Create alert rule in Prometheus
2. Configure Alertmanager
3. Set up notification channels
4. Test alerts

### Alert Channels

**Email:**
```yaml
receivers:
  - name: 'email'
    email_configs:
      - to: 'admin@example.com'
```

**Slack:**
```yaml
receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/...'
        channel: '#alerts'
```

## Troubleshooting Monitoring

### Prometheus Not Scraping

```bash
# Check Prometheus config
docker-compose exec prometheus cat /etc/prometheus/prometheus.yml

# Check targets
curl http://localhost:9090/api/v1/targets
```

### Grafana Can't Connect to Prometheus

- Verify Prometheus is running
- Check datasource configuration
- Verify network connectivity

### Traces Not Appearing

- Check Tempo is running
- Verify OpenTelemetry Collector
- Check trace export in logs
- Verify trace retention period

## Best Practices

1. **Regular Review**: Check dashboards daily
2. **Set Alerts**: For critical metrics
3. **Monitor Costs**: Track token usage
4. **Review Traces**: For failed cases
5. **Capacity Planning**: Monitor resource usage

## Next Steps

- [Docker Guide](docker.md)
- [Production Deployment](production.md)

