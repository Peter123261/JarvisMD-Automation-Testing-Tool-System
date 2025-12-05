# Monitoring Stack

Complete overview of the observability and monitoring infrastructure.

## Stack Components

```
┌─────────────────────────────────────────────────────────┐
│              Application Services                       │
│  API Gateway | Celery Workers                          │
│  (OpenTelemetry Instrumentation)                        │
└──────────────┬──────────────────────────────────────────┘
               │
               │ Traces & Metrics
               │
┌──────────────▼──────────────────────────────────────────┐
│      OpenTelemetry Collector                            │
│      - Receives traces via OTLP                         │
│      - Batches and exports                              │
└──────────────┬──────────────────┬───────────────────────┘
               │                  │
      ┌────────▼────────┐  ┌─────▼──────────┐
      │     Tempo       │  │   Prometheus    │
      │  (Traces)       │  │   (Metrics)      │
      └────────┬────────┘  └─────┬────────────┘
               │                 │
      ┌────────▼─────────────────▼──────────┐
      │         Grafana                      │
      │    - Trace Visualization            │
      │    - Metric Dashboards               │
      │    - Alert Management                │
      └──────────────────────────────────────┘
               │
      ┌────────▼────────┐
      │  Alertmanager   │
      │  - Alert Routing│
      │  - Notifications│
      └─────────────────┘
```

## Prometheus

### Purpose

Time-series database for metrics collection and storage.

### Configuration

**Location:** `monitoring/prometheus.yml`

**Scrape Targets:**
- API Gateway: `host.docker.internal:8007`
- Celery Worker: `host.docker.internal:8006`
- Node Exporter: `node-exporter:9100`
- cAdvisor: `host.docker.internal:8080`
- OpenTelemetry Collector: `otel-collector:8889`

**Retention:** 7 days (configurable)

### Metrics Collected

**Application Metrics:**
- `evaluations_total`: Total evaluations
- `evaluations_success_total`: Successful evaluations
- `evaluations_failed_total`: Failed evaluations
- `evaluation_duration_seconds`: Processing time histogram
- `evaluation_success_rate`: Success rate gauge
- `cases_flagged_total`: Flagged cases counter
- `tokens_input_total`: Input tokens
- `tokens_output_total`: Output tokens
- `tokens_total`: Total tokens

**System Metrics:**
- CPU usage
- Memory usage
- Disk usage
- Network I/O
- Container metrics

### Access

- **URL**: http://localhost:9090
- **Query Language**: PromQL
- **Retention**: 7 days

## Grafana

### Purpose

Visualization and dashboard platform for metrics and traces.

### Configuration

**Location:** `monitoring/grafana/`

**Datasources:**
- Prometheus (metrics)
- Tempo (traces)

**Dashboards:**
- System Overview
- Medical Evaluation Analytics
- Container Overview

### Features

- **Metrics Visualization**: Charts, graphs, tables
- **Trace Visualization**: Timeline view, span details
- **Alert Management**: View and manage alerts
- **Dashboard Sharing**: Export/import dashboards

### Access

- **URL**: http://localhost:3000
- **Default Credentials**: admin/admin
- **Change on first login**

## Tempo

### Purpose

Distributed trace storage and querying.

### Configuration

**Location:** `monitoring/tempo-config.yml`

**Storage:**
- Backend: Local filesystem
- Retention: 7 days (configurable)

**Features:**
- TraceQL query language
- Trace search
- Span filtering
- Error tracking

### Trace Structure

```
Trace (trace_id)
  ├── Span: POST /api/test/start
  │   ├── Span: run_batch_evaluation
  │   │   ├── Span: evaluate_single_case (case 1)
  │   │   │   ├── Span: llm_invoke
  │   │   │   └── Span: parse_evaluation_result
  │   │   ├── Span: evaluate_single_case (case 2)
  │   │   └── ...
```

### Access

- **API**: http://localhost:3200
- **Via Grafana**: Explore → Tempo datasource

## OpenTelemetry Collector

### Purpose

Collect, process, and export traces from all services.

### Configuration

**Location:** `monitoring/otel-collector-config.yml`

**Receivers:**
- OTLP (gRPC): Port 4317
- OTLP (HTTP): Port 4318

**Processors:**
- Batch: Groups spans (10 spans or 100ms timeout)
- Memory limiter: Prevents OOM

**Exporters:**
- OTLP to Tempo: Exports traces
- Prometheus: Exports metrics (port 8889)

### Batch Processing

- **Timeout**: 100ms (fast export)
- **Batch Size**: 10 spans (small batches)
- **Benefits**: Low latency, fast trace visibility

## Alertmanager

### Purpose

Route and manage alerts from Prometheus.

### Configuration

**Location:** `monitoring/alertmanager.yml`

**Alert Rules:**
- Low success rate
- High error rate
- System resource issues

### Features

- Alert grouping
- Deduplication
- Routing rules
- Notification channels (email, Slack, etc.)

### Access

- **URL**: http://localhost:9093
- **Alerts**: View active alerts
- **Silences**: Suppress alerts

## OpenTelemetry Instrumentation

### Automatic Instrumentation

**FastAPI:**
- HTTP requests/responses
- Route tracing
- Error capture

**Celery:**
- Task execution
- Retry tracking
- Error capture

**SQLAlchemy:**
- Database queries
- Connection pooling
- Transaction tracking

### Manual Instrumentation

**Evaluation Engine:**
```python
with tracer.start_as_current_span("evaluate_single_case") as span:
    # Evaluation logic
    span.set_attribute("case_id", case_id)
    span.set_status(Status(StatusCode.OK))
```

**Error Handling:**
```python
span.set_status(Status(StatusCode.ERROR, error_message))
span.set_attribute("error", True)
span.set_attribute("error.type", error_type)
span.record_exception(exception)
```

## Metrics Endpoints

### API Gateway Metrics

- **URL**: http://localhost:8007/metrics
- **Format**: Prometheus text format
- **Scraped by**: Prometheus every 10s

### Celery Worker Metrics

- **URL**: http://localhost:8006/metrics
- **Format**: Prometheus text format
- **Scraped by**: Prometheus every 10s

## Dashboards

### System Overview

- Service health status
- Container resource usage
- Network metrics
- System alerts

### Medical Evaluation Analytics

- Evaluation counts
- Success/failure rates
- Processing times (P50, P95, P99)
- Token usage
- Flagged cases
- Cost estimates

### Container Overview

- CPU usage per container
- Memory usage per container
- Network I/O
- Container restarts

## Alert Rules

### Evaluation Alerts

**Low Success Rate:**
- Trigger: Success rate < 80% for 5 minutes
- Severity: Warning

**High Failure Rate:**
- Trigger: Failure rate > 20% for 5 minutes
- Severity: Critical

### System Alerts

**High CPU Usage:**
- Trigger: CPU > 90% for 5 minutes
- Severity: Warning

**High Memory Usage:**
- Trigger: Memory > 90% for 5 minutes
- Severity: Warning

## Trace Analysis

### Viewing Traces

1. Get trace_id from results
2. Open Grafana → Explore
3. Select Tempo datasource
4. Enter trace_id or use TraceQL

### TraceQL Examples

```
# Find traces with errors
{status=error}

# Find slow evaluations
{duration>5s}

# Find specific job
{job_id="abc123..."}
```

### Span Attributes

**Common Attributes:**
- `trace_id`: Unique trace identifier
- `span.name`: Operation name
- `span.status`: OK or ERROR
- `error`: true/false
- `error.type`: Error type
- `error.message`: Error message
- `evaluation.duration_seconds`: Processing time
- `llm.model`: Model used
- `result.flagged`: Whether case is flagged

## Best Practices

1. **Monitor Key Metrics**: Success rate, processing time, error rate
2. **Set Up Alerts**: For critical issues
3. **Review Traces**: For failed cases
4. **Track Costs**: Monitor token usage
5. **Regular Review**: Check dashboards daily

## Next Steps

- [System Overview](system-overview.md)
- [Components](components.md)
- [Data Flow](data-flow.md)

