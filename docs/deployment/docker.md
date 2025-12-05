# Docker Deployment

Complete guide to Docker deployment for the MedBench Automation Testing Tool.

## Docker Compose Services

### Service Overview

The system consists of 12 Docker services:

1. **postgres**: PostgreSQL database
2. **redis**: Redis message broker
3. **api**: FastAPI application
4. **celery-worker**: Celery task workers
5. **celery-beat**: Celery scheduler
6. **flower**: Celery monitoring
7. **prometheus**: Metrics collection
8. **grafana**: Visualization
9. **alertmanager**: Alert routing
10. **node-exporter**: Host metrics
11. **cadvisor**: Container metrics
12. **otel-collector**: Trace collection
13. **tempo**: Trace storage

## Starting Services

### Start All Services

```bash
# Start in detached mode
docker-compose up -d

# Start with logs
docker-compose up
```

### Start Specific Services

```bash
# Start only infrastructure
docker-compose up -d postgres redis

# Start application services
docker-compose up -d api celery-worker
```

## Managing Services

### View Status

```bash
# List all services
docker-compose ps

# Check specific service
docker-compose ps api
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f celery-worker

# Last 100 lines
docker-compose logs --tail=100 api
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart api
docker-compose restart celery-worker
```

### Stop Services

```bash
# Stop all services
docker-compose stop

# Stop specific service
docker-compose stop api
```

### Remove Services

```bash
# Stop and remove containers
docker-compose down

# Remove containers and volumes (WARNING: Deletes data)
docker-compose down -v
```

## Rebuilding Images

### Rebuild After Code Changes

```bash
# Rebuild specific service
docker-compose build --no-cache api
docker-compose restart api

# Rebuild all services
docker-compose build --no-cache
docker-compose up -d
```

### Force Rebuild

```bash
# Remove old images and rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Volume Management

### Persistent Volumes

Data is stored in Docker volumes:

- `postgres_data`: Database data
- `redis_data`: Redis data
- `prometheus_data`: Metrics data
- `grafana_data`: Grafana data
- `tempo_data`: Trace data
- `alertmanager_data`: Alert data

### Backup Volumes

```bash
# Backup PostgreSQL
docker run --rm -v medbench-automation_postgres_data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_backup.tar.gz /data

# Restore PostgreSQL
docker run --rm -v medbench-automation_postgres_data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_backup.tar.gz -C /
```

## Network Configuration

### Default Network

All services run on `medbench-network` (bridge driver).

### Port Mapping

- `8000`: API Gateway
- `3000`: Grafana
- `5432`: PostgreSQL
- `6379`: Redis
- `9090`: Prometheus
- `9093`: Alertmanager
- `3200`: Tempo
- `5555`: Flower

### Custom Ports

Edit `docker-compose.yml` to change ports:

```yaml
ports:
  - "${API_PORT:-8000}:8000"  # Change 8000 to custom port
```

## Environment Variables

### Service-Specific Variables

Each service can have different environment variables:

```yaml
api:
  environment:
    - OPENAI_API_KEY=${OPENAI_API_KEY}
    - DATABASE_URL=postgresql://...
```

### Using .env File

Variables in `.env` are automatically loaded:

```bash
# .env
OPENAI_API_KEY=your_key
API_PORT=8000
```

## Health Checks

### Service Health

```bash
# Check API health
curl http://localhost:8000/api/health

# Check database
docker-compose exec postgres pg_isready

# Check Redis
docker-compose exec redis redis-cli ping
```

### Container Health

```bash
# View health status
docker-compose ps

# Check specific container
docker inspect medbench-api | grep Health
```

## Scaling Services

### Scale Workers

```bash
# Scale to 8 workers
docker-compose up -d --scale celery-worker=8
```

### Load Balancing

For API Gateway, use a reverse proxy:

```yaml
# Add nginx service
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
  depends_on:
    - api
```

## Resource Limits

### Set Resource Limits

```yaml
api:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 1G
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs api

# Check container status
docker-compose ps

# Inspect container
docker inspect medbench-api
```

### Port Conflicts

```bash
# Check what's using port
netstat -an | grep 8000

# Change port in docker-compose.yml
```

### Volume Issues

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect medbench-automation_postgres_data

# Remove volume (WARNING: Deletes data)
docker volume rm medbench-automation_postgres_data
```

## Production Considerations

### Security

- Use strong passwords
- Enable TLS/SSL
- Restrict port exposure
- Use secrets management
- Regular security updates

### Performance

- Set resource limits
- Use production images
- Enable connection pooling
- Optimize database queries
- Monitor resource usage

### Backup

- Regular database backups
- Volume snapshots
- Configuration backups
- Disaster recovery plan

## Next Steps

- [Production Deployment](production.md)
- [Monitoring Setup](monitoring.md)

