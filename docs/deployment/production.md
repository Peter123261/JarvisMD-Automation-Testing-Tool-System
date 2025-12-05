# Production Deployment

Production deployment checklist and best practices.

## Pre-Deployment Checklist

### Security

- [ ] Change all default passwords
- [ ] Use strong `POSTGRES_PASSWORD`
- [ ] Set `DEBUG=false`
- [ ] Configure `CORS_ORIGINS` to specific domains
- [ ] Enable HTTPS/TLS
- [ ] Set up firewall rules
- [ ] Use secrets management
- [ ] Rotate API keys regularly

### Configuration

- [ ] Review all environment variables
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure production database
- [ ] Set up monitoring alerts
- [ ] Configure backup schedule
- [ ] Set resource limits
- [ ] Enable log rotation

### Infrastructure

- [ ] Provision sufficient resources
- [ ] Set up load balancer (if needed)
- [ ] Configure DNS
- [ ] Set up SSL certificates
- [ ] Configure backup storage
- [ ] Set up monitoring
- [ ] Plan for scaling

## Production Configuration

### Environment Variables

```bash
# Production .env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Strong passwords
POSTGRES_PASSWORD=<strong-random-password>
GRAFANA_ADMIN_PASSWORD=<strong-random-password>

# Restricted CORS
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Production database
DATABASE_URL=postgresql://user:pass@postgres:5432/jarvismd

# Monitoring
GRAFANA_URL=https://grafana.yourdomain.com
TEMPO_URL=http://tempo:3200
```

### Docker Compose Production

Use `docker-compose.prod.yml`:

```yaml
# Override development settings
api:
  build:
    target: production  # Use production stage
  environment:
    - DEBUG=false
    - LOG_LEVEL=INFO
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
```

### Start Production

```bash
# Use production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Security Hardening

### Network Security

- Use internal Docker network
- Expose only necessary ports
- Use reverse proxy (nginx/traefik)
- Enable firewall rules
- Use VPN for admin access

### Application Security

- Input validation
- SQL injection prevention (SQLAlchemy handles this)
- XSS prevention
- CSRF protection
- Rate limiting
- Authentication/authorization

### Data Security

- Encrypt database connections
- Encrypt sensitive data at rest
- Regular security updates
- Access control
- Audit logging

## Performance Optimization

### Database

```yaml
postgres:
  environment:
    - POSTGRES_INITDB_ARGS: "-E UTF8"
  command:
    - "postgres"
    - "-c"
    - "max_connections=200"
    - "-c"
    - "shared_buffers=256MB"
    - "-c"
    - "effective_cache_size=1GB"
```

### Celery Workers

```yaml
celery-worker:
  command: celery ... --concurrency=8  # Increase for production
  deploy:
    resources:
      limits:
        cpus: '4'
        memory: 4G
```

### API Gateway

```yaml
api:
  command: uvicorn ... --workers 4  # Multiple workers
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
```

## Monitoring

### Set Up Alerts

Configure Alertmanager for:
- High error rates
- Low success rates
- Resource exhaustion
- Service downtime

### Dashboard Access

- Secure Grafana access
- Use strong passwords
- Enable 2FA if available
- Restrict access to authorized users

## Backup Strategy

### Database Backups

```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

docker-compose exec -T postgres pg_dump -U medbench jarvismd > \
  $BACKUP_DIR/db_backup_$DATE.sql

# Keep last 30 days
find $BACKUP_DIR -name "db_backup_*.sql" -mtime +30 -delete
```

### Volume Backups

```bash
# Backup all volumes
docker run --rm \
  -v medbench-automation_postgres_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/postgres_$(date +%Y%m%d).tar.gz /data
```

## Scaling

### Horizontal Scaling

**API Gateway:**
- Multiple instances behind load balancer
- Session affinity not required (stateless)

**Celery Workers:**
- Scale workers independently
- Add more workers for higher throughput

**Database:**
- Read replicas for queries
- Connection pooling
- Query optimization

### Vertical Scaling

- Increase container resources
- Optimize application code
- Database tuning
- Cache frequently accessed data

## Disaster Recovery

### Recovery Plan

1. **Backup Verification**: Regularly test backups
2. **Recovery Procedures**: Document restore steps
3. **RTO/RPO**: Define recovery objectives
4. **Testing**: Regular disaster recovery drills

### Backup Locations

- On-premises backup server
- Cloud storage (S3, Azure Blob)
- Multiple geographic locations

## Maintenance

### Regular Tasks

- **Daily**: Monitor alerts and logs
- **Weekly**: Review performance metrics
- **Monthly**: Security updates, backup verification
- **Quarterly**: Capacity planning, disaster recovery test

### Updates

```bash
# Update application
git pull
docker-compose build --no-cache
docker-compose up -d

# Update dependencies
pip install -r requirements.txt --upgrade
npm update
```

## Health Checks

### Automated Health Checks

```bash
#!/bin/bash
# health_check.sh

API_HEALTH=$(curl -s http://localhost:8000/api/health | jq -r '.status')
DB_HEALTH=$(docker-compose exec -T postgres pg_isready -U medbench)

if [ "$API_HEALTH" != "healthy" ] || [ -z "$DB_HEALTH" ]; then
  echo "Health check failed"
  exit 1
fi
```

### Monitoring Integration

- Prometheus health checks
- Grafana alerting
- External monitoring (Pingdom, UptimeRobot)

## Next Steps

- [Docker Guide](docker.md)
- [Monitoring Setup](monitoring.md)

