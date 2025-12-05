# System Overview

High-level architecture of the MedBench Automation Testing Tool.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │Dashboard │  │TestRunner│  │ Results  │  │Analytics │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
└───────┼──────────────┼──────────────┼──────────────┼────────────┘
        │              │              │              │
        └──────────────┴──────────────┴──────────────┘
                           │
        ┌──────────────────▼──────────────────┐
        │      API Gateway (FastAPI)            │
        │  ┌────────────────────────────────┐  │
        │  │  Routes                         │  │
        │  │  - /api/evaluate               │  │
        │  │  - /api/results                │  │
        │  │  - /api/health                 │  │
        │  └────────────────────────────────┘  │
        │  ┌────────────────────────────────┐  │
        │  │  Evaluation Engine (Singleton)   │  │
        │  │  - LLM Integration               │  │
        │  │  - Prompt Management             │  │
        │  │  - Score Calculation             │  │
        │  └────────────────────────────────┘  │
        └──────────┬───────────────────┬─────────┘
                   │                   │
        ┌──────────▼──────────┐  ┌─────▼──────────────┐
        │  Celery Task Queue  │  │  PostgreSQL DB     │
        │  - Worker Pool       │  │  - TestJobs        │
        │  - Task Distribution │  │  - Results        │
        │  - Retry Logic       │  │  - Alerts         │
        └──────────┬──────────┘  └────────────────────┘
                   │
        ┌──────────▼──────────┐
        │  Redis (Broker)      │
        │  - Message Queue     │
        │  - Result Backend    │
        └─────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Observability Stack                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │Prometheus│  │ Grafana  │  │  Tempo   │  │Alertmgr  │       │
│  │(Metrics) │  │(Viz)     │  │(Traces)  │  │(Alerts)  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │     OpenTelemetry Collector                               │  │
│  │     - Trace Collection                                    │  │
│  │     - Span Export                                         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## System Layers

### 1. Presentation Layer

**Frontend (React/TypeScript)**
- User interface components
- API client for backend communication
- Real-time updates via polling
- Data visualization

**Technologies:**
- React 19.1+
- TypeScript
- Material-UI v7
- React Query
- Recharts

### 2. Application Layer

**API Gateway (FastAPI)**
- RESTful API endpoints
- Request validation
- Authentication/authorization
- Response formatting

**Evaluation Engine**
- Singleton pattern for efficiency
- LLM integration (LangChain)
- Prompt management
- Score calculation
- Error handling

**Technologies:**
- FastAPI
- LangChain
- OpenAI API
- SQLAlchemy

### 3. Business Logic Layer

**Task Queue System (Celery)**
- Async task processing
- Worker pool management
- Retry logic
- Progress tracking

**Technologies:**
- Celery
- Redis
- Thread pool execution

### 4. Data Layer

**PostgreSQL Database**
- Persistent storage
- Transaction management
- Data relationships

**Models:**
- TestJob
- EvaluationResult
- AlertQueue
- SystemMetric

**Technologies:**
- PostgreSQL
- SQLAlchemy ORM

### 5. Infrastructure Layer

**Message Broker (Redis)**
- Task queue
- Result backend
- Caching

**Monitoring Stack**
- Prometheus (metrics)
- Grafana (visualization)
- Tempo (traces)
- Alertmanager (alerts)
- OpenTelemetry (instrumentation)

## Data Flow

### Evaluation Request Flow

1. **User submits evaluation request** (UI or API)
2. **API Gateway receives request**
   - Validates input
   - Creates TestJob record
   - Returns job_id

3. **Task queued to Celery**
   - Job queued in Redis
   - Worker picks up task

4. **Worker processes cases**
   - Loads case data
   - Calls Evaluation Engine
   - Saves results to database
   - Updates progress

5. **Results available**
   - Job status: completed
   - Results queryable via API
   - UI displays results

### Evaluation Engine Flow

1. **Load prompt template** (cached)
2. **Initialize LLM** (singleton)
3. **Invoke LLM** with case data
4. **Parse response** (JSON extraction)
5. **Calculate scores** (24 criteria)
6. **Assess complexity** (5 dimensions)
7. **Return results** with trace_id

## Component Interactions

### API Gateway ↔ Database

- Create/read TestJob records
- Store EvaluationResult records
- Query results and summaries
- Update job status

### API Gateway ↔ Celery

- Queue evaluation tasks
- Check task status
- Cancel tasks
- Get task results

### Celery ↔ Evaluation Engine

- Worker calls engine for each case
- Engine processes case
- Results returned to worker
- Worker saves to database

### Evaluation Engine ↔ OpenAI

- LLM API calls
- Token usage tracking
- Error handling
- Rate limit management

### All Services ↔ OpenTelemetry

- Automatic instrumentation
- Span creation
- Trace export
- Error recording

## Scalability

### Horizontal Scaling

- **API Gateway**: Multiple instances behind load balancer
- **Celery Workers**: Scale workers independently
- **Database**: Read replicas for queries
- **Redis**: Cluster mode for high availability

### Vertical Scaling

- **Worker Concurrency**: Increase per-worker threads
- **Database**: Increase connection pool size
- **Memory**: Adjust for larger batches

## Security

### Authentication

- Currently: None (development)
- Production: API keys or OAuth2

### Data Protection

- Environment variables for secrets
- Database connection encryption
- CORS protection
- Input validation

### Network Security

- Internal Docker network
- Port exposure control
- Service isolation

## Performance Characteristics

### Throughput

- **Single Worker**: ~5 cases/minute
- **4 Workers**: ~20 cases/minute
- **Scales linearly** with worker count

### Latency

- **P50**: ~2 seconds per case
- **P95**: ~3 seconds per case
- **P99**: ~5 seconds per case

### Resource Usage

- **API**: ~200MB RAM
- **Worker**: ~500MB RAM per worker
- **Database**: ~100MB RAM
- **Redis**: ~50MB RAM

## Next Steps

- [Component Details](components.md)
- [Data Flow](data-flow.md)
- [Monitoring Stack](monitoring-stack.md)

