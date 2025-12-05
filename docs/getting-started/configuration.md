# Configuration Guide

Complete guide to configuring the MedBench Automation Testing Tool.

## Environment Variables

All configuration is done through environment variables in the `.env` file.

### OpenAI Configuration

```bash
# Required: Your OpenAI API key
OPENAI_API_KEY=sk-your-api-key-here

# Default model to use for evaluations
DEFAULT_MODEL=gpt-4o

# Alternative models: gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo
```

### Database Configuration

```bash
# PostgreSQL Configuration
POSTGRES_USER=medbench
POSTGRES_PASSWORD=medbench_secure_password_change_in_production
POSTGRES_DB=jarvismd
POSTGRES_PORT=5432
POSTGRES_HOST=postgres
```

### API Configuration

```bash
# API Server
API_PORT=8000
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# CORS Origins (comma-separated)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173

# Debug Mode
DEBUG=true
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### Redis Configuration

```bash
# Redis Connection
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Celery Configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_POOL=threads
```

### Monitoring Configuration

```bash
# Grafana
GRAFANA_URL=http://localhost:3000
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin

# Tempo (Distributed Tracing)
TEMPO_URL=http://localhost:3200

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

# Prometheus Metrics
API_METRICS_HOST=0.0.0.0
API_METRICS_PORT=8007
WORKER_METRICS_HOST=0.0.0.0
WORKER_METRICS_PORT=8002
WORKER_METRICS_EXTERNAL_PORT=8006
```

### Flower (Celery Monitoring)

```bash
FLOWER_PORT=5555
FLOWER_USER=admin
FLOWER_PASSWORD=admin
FLOWER_UNAUTHENTICATED_API=true
```

### Evaluation Configuration

```bash
# Maximum concurrent evaluations
MAX_CONCURRENT_EVALUATIONS=5

# Use Celery for batch processing
USE_CELERY_BATCH=true
```

## Configuration Files

### docker-compose.yml

Main Docker Compose configuration. Key sections:

- **Services**: API, database, Redis, monitoring stack
- **Networks**: Internal Docker network
- **Volumes**: Data persistence

### Monitoring Configuration

Located in `monitoring/` directory:

- `prometheus.yml` - Prometheus scrape configuration
- `alert_rules.yml` - Alerting rules
- `alertmanager.yml` - Alert routing
- `tempo-config.yml` - Trace storage configuration
- `otel-collector-config.yml` - Trace collection

### Frontend Configuration

Frontend uses environment variables prefixed with `VITE_`:

```bash
# In frontend/.env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_GRAFANA_URL=http://localhost:3000
```

## Configuration by Environment

### Development

```bash
DEBUG=true
LOG_LEVEL=DEBUG
ENVIRONMENT=development
RELOAD=true
```

### Production

```bash
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=production
RELOAD=false

# Use strong passwords
POSTGRES_PASSWORD=<strong-password>
GRAFANA_ADMIN_PASSWORD=<strong-password>
```

## Validation

### Check Configuration

```bash
# Test API configuration
curl http://localhost:8000/api/health

# Test database connection
docker-compose exec api python -c "from jarvismd.backend.database.database import get_database; get_database().test_connection()"

# Test Redis connection
docker-compose exec redis redis-cli ping
```

### Verify Environment Variables

```bash
# Check if variables are loaded
docker-compose exec api env | grep OPENAI
docker-compose exec api env | grep DATABASE
```

## Security Considerations

### Production Checklist

- [ ] Change all default passwords
- [ ] Use strong `POSTGRES_PASSWORD`
- [ ] Set `DEBUG=false`
- [ ] Configure `CORS_ORIGINS` to specific domains
- [ ] Use environment-specific `.env` files
- [ ] Never commit `.env` to version control
- [ ] Rotate API keys regularly
- [ ] Use secrets management (e.g., Docker secrets, Kubernetes secrets)

### API Key Security

- Store API keys in `.env` file (not in code)
- Use different keys for dev/staging/production
- Monitor API key usage in OpenAI dashboard
- Set usage limits in OpenAI account

## Advanced Configuration

### Custom Prompts

Add custom prompt files to `jarvismd/data/prompts/`:

```bash
# Example: custom_benchmark.txt
# The system will automatically detect and make it available
```

### Database Tuning

For PostgreSQL in production:

```yaml
# In docker-compose.yml
postgres:
  environment:
    POSTGRES_INITDB_ARGS: "-E UTF8 --locale=C"
  command:
    - "postgres"
    - "-c"
    - "max_connections=200"
    - "-c"
    - "shared_buffers=256MB"
```

### Celery Worker Scaling

Adjust worker concurrency:

```bash
# In docker-compose.yml
celery-worker:
  command: celery ... --concurrency=8  # Increase from default 4
```

## Troubleshooting Configuration

### Environment Variables Not Loading

```bash
# Verify .env file location (should be in project root)
ls -la .env

# Check if variables are in docker-compose.yml
docker-compose config
```

### Configuration Conflicts

```bash
# View effective configuration
docker-compose config

# Check service-specific environment
docker-compose exec api env
```

## Next Steps

- [Run your first evaluation](first-evaluation.md)
- [Learn about the architecture](../architecture/)

