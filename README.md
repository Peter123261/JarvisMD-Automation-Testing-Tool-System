# MedBench Automation Testing Tool

> A comprehensive medical case evaluation system using LLM technology for automated quality assessment of AI-generated medical recommendations.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.1+-blue.svg)](https://reactjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 Overview

MedBench Automation Testing Tool is a production-ready system for evaluating AI-generated medical recommendations against established clinical benchmarks. The system provides:

- **Automated Evaluation**: Batch processing of medical cases using LLM technology
- **Comprehensive Scoring**: 24-criteria evaluation framework with complexity assessment
- **Real-time Monitoring**: Full observability stack with Prometheus, Grafana, and distributed tracing
- **Cost Optimization**: Singleton pattern and resource caching for efficient API usage
- **Flagged Case Management**: Automatic identification of cases requiring review (score < 75%)
- **Distributed Tracing**: OpenTelemetry integration for end-to-end traceability

## ✨ Key Features

### Core Functionality
- **Medical Case Evaluation**: Evaluate AI-generated recommendations using APPRAISE-AI benchmark
- **Batch Processing**: Process multiple cases concurrently with Celery task queue
- **Dynamic Criteria Parsing**: Automatically extract evaluation criteria from prompt files
- **Token Usage Tracking**: Monitor and track LLM API usage and costs
- **Error Handling**: Comprehensive error logging with full tracebacks

### Observability & Monitoring
- **Distributed Tracing**: OpenTelemetry traces with Tempo backend
- **Metrics Collection**: Prometheus metrics for system performance
- **Visualization**: Grafana dashboards for analytics and monitoring
- **Alerting**: Alertmanager for critical system events
- **Health Checks**: Multi-level health monitoring endpoints

### User Interface
- **Dashboard**: Real-time system overview and quick actions
- **Test Runner**: Start and monitor evaluation jobs
- **Results Viewer**: Detailed results with criteria breakdown
- **Analytics**: Performance metrics and cost analysis
- **Trace Viewer**: Direct links to distributed traces in Grafana

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│  Dashboard | Test Runner | Results | Analytics              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              API Gateway (FastAPI)                           │
│  /api/evaluate | /api/results | /api/health                 │
└───────────────┬──────────────────────┬──────────────────────┘
                │                      │
    ┌───────────▼──────────┐  ┌────────▼──────────┐
    │  Evaluation Engine   │  │  Celery Workers   │
    │  (Singleton LLM)     │  │  (Async Tasks)    │
    └───────────┬──────────┘  └────────┬──────────┘
                │                      │
    ┌───────────▼──────────────────────▼──────────┐
    │         PostgreSQL Database                   │
    │  TestJobs | EvaluationResults | Alerts        │
    └──────────────────────────────────────────────┘
                │
    ┌───────────▼──────────────────────────────────┐
    │      Monitoring Stack                        │
    │  Prometheus | Grafana | Tempo | Alertmanager │
    └──────────────────────────────────────────────┘
```

### Technology Stack

**Backend:**
- FastAPI (Python web framework)
- SQLAlchemy (ORM)
- Celery (Async task queue)
- Redis (Message broker)
- PostgreSQL (Database)
- LangChain (LLM integration)
- OpenTelemetry (Distributed tracing)

**Frontend:**
- React 19.1+ (UI framework)
- TypeScript (Type safety)
- Material-UI v7 (Component library)
- React Query (Data fetching)
- Recharts (Data visualization)

**Infrastructure:**
- Docker & Docker Compose (Containerization)
- Prometheus (Metrics)
- Grafana (Visualization)
- Tempo (Trace storage)
- Alertmanager (Alerting)
- OpenTelemetry Collector (Trace collection)

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenAI API key
- 8GB+ RAM recommended
- Ports: 8000, 3000, 5432, 6379, 9090, 9093, 3200

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd medbench-automation
   ```

2. **Configure environment**
   ```bash
   # Copy .env file (if not exists)
   cp .env.example .env
   
   # Edit .env and add your OpenAI API key
   OPENAI_API_KEY=your_api_key_here
   ```

3. **Start the system**
   ```bash
   docker-compose up -d
   ```

4. **Verify services**
   ```bash
   # Check all services are running
   docker-compose ps
   
   # Check API health
   curl http://localhost:8000/api/health
   ```

5. **Access the UI**
   - Frontend: http://localhost:5173 (if running dev mode)
   - API Docs: http://localhost:8000/api/docs
   - Grafana: http://localhost:3000 (admin/admin)
   - Prometheus: http://localhost:9090
   - Flower (Celery): http://localhost:5555

### First Evaluation

1. **Start the frontend** (if not using Docker)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

2. **Navigate to Test Runner**
   - Open http://localhost:5173
   - Go to "Test Runner" page
   - Select benchmark (e.g., `appraise_v2`)
   - Enter number of cases
   - Click "Start Evaluation"

3. **Monitor progress**
   - View real-time updates in Dashboard
   - Check job status in Results page
   - View traces in Grafana

## 📚 Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[Getting Started](docs/getting-started/)** - Installation, configuration, first evaluation
- **[User Guides](docs/user-guides/)** - Running evaluations, viewing results, understanding scores
- **[Architecture](docs/architecture/)** - System overview, components, data flow
- **[API Reference](docs/api/)** - Endpoints, authentication, examples
- **[Development](docs/development/)** - Setup, contributing, testing
- **[Deployment](docs/deployment/)** - Docker, production, monitoring

## 🔧 Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_key_here
DEFAULT_MODEL=gpt-4o

# Database
POSTGRES_USER=medbench
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=jarvismd

# API Configuration
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Monitoring
GRAFANA_URL=http://localhost:3000
TEMPO_URL=http://localhost:3200
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

See [Configuration Guide](docs/getting-started/configuration.md) for complete list.

## 📊 System Components

### Evaluation Engine
- Singleton pattern for resource efficiency
- Cached LLM instances and prompt templates
- Cost tracking and token usage monitoring
- Error handling with full tracebacks

### Task Queue System
- Celery workers for async processing
- Redis message broker
- Retry logic for failed cases
- Progress tracking and status updates

### Database Models
- `TestJob`: Evaluation job tracking
- `EvaluationResult`: Individual case results
- `AlertQueue`: Flagged cases for review
- `SystemMetric`: Performance metrics

### Monitoring Stack
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **Tempo**: Distributed trace storage
- **Alertmanager**: Alert routing
- **OpenTelemetry**: Trace instrumentation

## 🎓 Evaluation Framework

The system uses the **APPRAISE-AI** benchmark with:

- **24 Evaluation Criteria**: Covering safety, quality, reasoning, and clarity
- **Complexity Assessment**: 5-dimensional framework (25 points)
- **Scoring System**: Dynamic max scores per criterion
- **Safety Criteria**: Special handling for critical safety checks
- **Flagging System**: Automatic flagging for scores < 75%

See [Understanding Scores](docs/user-guides/understanding-scores.md) for details.

## 🔍 Monitoring & Observability

### Metrics Available
- Evaluation success/failure rates
- Processing times (P50, P95, P99)
- Token usage (input, output, total)
- Flagged cases count
- System resource usage

### Distributed Tracing
- End-to-end trace visibility
- Span-level error tracking
- Performance bottleneck identification
- Trace links in UI for easy debugging

### Dashboards
- **System Overview**: Service health and status
- **Medical Evaluation Analytics**: Evaluation metrics
- **Container Overview**: Resource usage

## 🛠️ Development

### Project Structure

```
medbench-automation/
├── jarvismd/              # Backend Python package
│   ├── backend/
│   │   ├── services/      # API gateway, evaluation engine
│   │   ├── database/      # Models and database setup
│   │   ├── automation/    # Celery tasks and workers
│   │   └── shared/         # Shared utilities
│   └── data/              # Medical cases and prompts
├── frontend/              # React frontend
│   └── src/
│       ├── pages/         # Main application pages
│       ├── components/    # Reusable components
│       └── services/      # API client
├── monitoring/            # Monitoring stack configs
├── docker-compose.yml     # Docker services
└── docs/                 # Documentation
```

### Running Locally

```bash
# Backend
cd jarvismd/backend/services/api_gateway
python -m uvicorn main:app --reload

# Frontend
cd frontend
npm run dev

# Celery Worker
celery -A jarvismd.backend.automation.task_queue.celery_app worker --loglevel=info
```

See [Development Setup](docs/development/setup.md) for detailed instructions.

## 🐳 Docker Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api
docker-compose logs -f celery-worker

# Rebuild after code changes
docker-compose build --no-cache api
docker-compose restart api

# Stop all services
docker-compose down

# Clean up (removes volumes)
docker-compose down -v
```

See [Docker Guide](docs/deployment/docker.md) for more commands.

## 📈 Performance

- **Concurrent Processing**: 4 Celery workers by default
- **Batch Size**: Configurable per evaluation
- **Cost Optimization**: 66% reduction through singleton pattern
- **Response Time**: < 3s per case (P95)
- **Throughput**: ~20 cases/minute (4 workers)

## 🔒 Security

- Environment variable configuration
- CORS protection
- Database connection pooling
- Non-root Docker user (production)
- Input validation and sanitization

## 🤝 Contributing

Contributions are welcome! Please see [Contributing Guide](docs/development/contributing.md) for:
- Code style guidelines
- Testing requirements
- Pull request process
- Issue reporting

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- APPRAISE-AI benchmark framework
- OpenAI for LLM API
- OpenTelemetry community
- All contributors

## 📞 Support

- **Documentation**: See `docs/` directory
- **Issues**: Open a GitHub issue
- **Questions**: Check troubleshooting guide

---

**Built Peter Olamojin**

