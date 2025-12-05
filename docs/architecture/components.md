# System Components

Detailed description of all system components.

## Backend Components

### API Gateway

**Location:** `jarvismd/backend/services/api_gateway/`

**Purpose:** Main entry point for all API requests

**Key Files:**
- `main.py`: FastAPI application setup
- `routes/`: API endpoint definitions
  - `evaluate.py`: Evaluation endpoints
  - `results.py`: Results and summary endpoints
  - `health.py`: Health check endpoints
- `schemas.py`: Pydantic models for request/response
- `settings.py`: Configuration management

**Responsibilities:**
- Request routing and validation
- Database session management
- Error handling
- OpenTelemetry instrumentation
- CORS configuration

### Evaluation Engine

**Location:** `jarvismd/backend/services/api_gateway/evaluation_engine.py`

**Purpose:** Core evaluation logic with LLM integration

**Key Features:**
- Singleton pattern for resource efficiency
- Cached LLM instances
- Cached prompt templates
- Score calculation
- Complexity assessment
- Error handling with tracebacks

**Methods:**
- `evaluate_single_case()`: Evaluate one case
- `evaluate_batch()`: Evaluate multiple cases
- `_parse_evaluation_result()`: Parse LLM response
- `_load_prompt_template()`: Load and cache prompts

**Metrics:**
- Evaluation counts
- Success/failure rates
- Processing times
- Token usage

### Prompt Parser

**Location:** `jarvismd/backend/services/api_gateway/prompt_parser.py`

**Purpose:** Extract criteria metadata from prompt files

**Key Features:**
- Dynamic criteria extraction
- Max score parsing
- Safety criteria detection
- Text normalization

**Methods:**
- `get_criteria_schema()`: Get full criteria schema
- `get_max_score()`: Get max score for criterion
- `_extract_criterion_texts()`: Parse criterion text
- `_extract_safety_criteria()`: Identify safety criteria

### Database Models

**Location:** `jarvismd/backend/database/models.py`

**Models:**

#### TestJob
- Tracks evaluation jobs
- Fields: id, benchmark, model, total_cases, status, timestamps
- Relationships: One-to-many with EvaluationResult

#### EvaluationResult
- Stores individual case results
- Fields: case_id, total_score, criteria_scores, trace_id, tokens
- Relationships: Many-to-one with TestJob, One-to-many with AlertQueue

#### AlertQueue
- Flags cases requiring review
- Fields: evaluation_result_id, alert_type, severity, score
- Relationships: Many-to-one with EvaluationResult

#### SystemMetric
- Tracks system performance
- Fields: metric_name, metric_value, test_job_id, timestamp

### Database Manager

**Location:** `jarvismd/backend/database/database.py`

**Purpose:** Database connection and initialization

**Features:**
- Supports SQLite (dev) and PostgreSQL (prod)
- Connection pooling
- Table creation and migration
- Session management

**Methods:**
- `init_database()`: Initialize database
- `create_tables()`: Create all tables
- `get_session()`: Get database session
- `test_connection()`: Verify connectivity

### Celery Application

**Location:** `jarvismd/backend/automation/task_queue/celery_app.py`

**Purpose:** Celery task queue configuration

**Features:**
- Redis broker configuration
- Task routing
- Worker configuration
- OpenTelemetry setup
- Prometheus metrics

**Configuration:**
- Task serialization: JSON
- Worker pool: threads
- Concurrency: 4 (configurable)
- Task timeouts: 30 minutes

### Evaluation Tasks

**Location:** `jarvismd/backend/automation/task_queue/tasks/evaluation_tasks.py`

**Purpose:** Celery tasks for evaluation processing

**Tasks:**

#### run_batch_evaluation
- Main batch evaluation task
- Processes multiple cases
- Handles retries
- Updates progress
- Saves results

#### run_single_case_evaluation
- Single case evaluation
- Used for individual cases
- Returns result immediately

**Features:**
- Retry logic (max 2 attempts)
- Progress tracking
- Error handling
- Trace ID extraction

### Error Logger

**Location:** `jarvismd/backend/shared/utils/error_logger.py`

**Purpose:** Centralized error logging

**Features:**
- Full traceback logging
- Context information
- Structured log format
- Multiple log levels

**Usage:**
```python
from jarvismd.backend.shared.utils.error_logger import log_full_error

log_full_error(
    error=exception,
    context={'job_id': '123', 'case_id': '456'},
    log_level='error'
)
```

## Frontend Components

### Pages

**Location:** `frontend/src/pages/`

#### Dashboard
- System overview
- Quick actions
- Real-time metrics
- Recent jobs

#### TestRunner
- Start evaluations
- Configure parameters
- Monitor progress
- Cancel jobs

#### Results
- View evaluation results
- Filter by job ID
- Detailed case breakdown
- Export results

#### Analytics
- Performance metrics
- Cost analysis
- Token usage
- Success rates

### Components

**Location:** `frontend/src/components/`

#### Common Components
- `SummaryCard`: Metric display cards
- `DataTable`: Reusable data table
- `StatusBadge`: Status indicators
- `LoadingSkeleton`: Loading states
- `EmptyState`: Empty state messages

#### Layout Components
- `Layout`: Main application layout
- Sidebar navigation
- Header with branding

### Services

**Location:** `frontend/src/services/`

#### API Service
- Axios client configuration
- Endpoint definitions
- Request/response handling
- Error handling

## Infrastructure Components

### Docker Services

**docker-compose.yml** defines:

#### API Service
- FastAPI application
- Port: 8000
- Dependencies: postgres, redis
- Volumes: prompts, medical_cases

#### Celery Worker
- Task processing
- Port: 8006 (metrics)
- Dependencies: postgres, redis
- Volumes: prompts, medical_cases

#### PostgreSQL
- Database storage
- Port: 5432
- Persistent volume
- Health checks

#### Redis
- Message broker
- Port: 6379
- Persistent volume
- Health checks

#### Monitoring Stack
- Prometheus (metrics)
- Grafana (visualization)
- Tempo (traces)
- Alertmanager (alerts)
- OpenTelemetry Collector

### Monitoring Configuration

**Location:** `monitoring/`

#### Prometheus
- `prometheus.yml`: Scrape configuration
- `alert_rules.yml`: Alerting rules
- `recording_rules.yml`: Metric aggregation

#### Grafana
- `dashboards/`: Pre-configured dashboards
- `provisioning/`: Datasource configuration

#### Tempo
- `tempo-config.yml`: Trace storage config
- Retention: 7 days (configurable)

#### OpenTelemetry
- `otel-collector-config.yml`: Trace collection
- Batch processing: 100ms timeout
- Export to Tempo

## Data Flow Components

### Request Flow

1. **Frontend** → API Gateway
2. **API Gateway** → Database (create job)
3. **API Gateway** → Celery (queue task)
4. **Celery** → Redis (store task)
5. **Worker** → Evaluation Engine
6. **Evaluation Engine** → OpenAI API
7. **Worker** → Database (save results)
8. **Frontend** → API Gateway (poll status)

### Trace Flow

1. **All Services** → OpenTelemetry SDK
2. **OpenTelemetry SDK** → Collector
3. **Collector** → Tempo
4. **Grafana** → Tempo (query traces)

### Metrics Flow

1. **Services** → Prometheus Client
2. **Prometheus** → Scrape endpoints
3. **Grafana** → Prometheus (query metrics)
4. **Alertmanager** → Prometheus (evaluate alerts)

## Next Steps

- [System Overview](system-overview.md)
- [Data Flow](data-flow.md)
- [Monitoring Stack](monitoring-stack.md)

