# Installation Guide

This guide will walk you through installing and setting up the MedBench Automation Testing Tool.

## Prerequisites

Before you begin, ensure you have the following installed:

### Required Software

- **Docker** (version 20.10+)
  - [Install Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Verify: `docker --version`
  
- **Docker Compose** (version 2.0+)
  - Usually included with Docker Desktop
  - Verify: `docker-compose --version`

- **Git** (for cloning the repository)
  - [Install Git](https://git-scm.com/downloads)
  - Verify: `git --version`

### System Requirements

- **RAM**: 8GB minimum, 16GB recommended
- **Disk Space**: 10GB free space
- **CPU**: 4 cores recommended
- **Operating System**: Windows 10+, macOS 10.15+, or Linux

### External Services

- **OpenAI API Key**: Required for LLM evaluations
  - Get your key from [OpenAI Platform](https://platform.openai.com/api-keys)
  - Ensure you have sufficient credits

### Port Requirements

The following ports must be available:
- `8000` - API Gateway
- `3000` - Grafana
- `5432` - PostgreSQL
- `6379` - Redis
- `9090` - Prometheus
- `9093` - Alertmanager
- `3200` - Tempo
- `5555` - Flower (Celery monitoring)
- `5173` - Frontend (development mode)

## Installation Steps

### 1. Clone the Repository

```bash
git clone <repository-url>
cd medbench-automation
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example file (if available)
cp .env.example .env

# Or create a new .env file
touch .env
```

Edit `.env` and add your configuration. Minimum required:

```bash
# OpenAI Configuration (REQUIRED)
OPENAI_API_KEY=sk-your-api-key-here
DEFAULT_MODEL=gpt-4o

# Database Configuration
POSTGRES_USER=medbench
POSTGRES_PASSWORD=medbench_secure_password_change_in_production
POSTGRES_DB=jarvismd

# API Configuration
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Monitoring URLs
GRAFANA_URL=http://localhost:3000
TEMPO_URL=http://localhost:3200
```

See [Configuration Guide](configuration.md) for all available options.

### 3. Start Docker Services

```bash
# Start all services in detached mode
docker-compose up -d

# Or start with logs visible
docker-compose up
```

This will:
- Build Docker images (first time only)
- Start all services (API, database, Redis, monitoring stack)
- Initialize the database
- Set up monitoring dashboards

### 4. Verify Installation

Check that all services are running:

```bash
# Check container status
docker-compose ps

# Expected output should show all services as "Up"
```

Test the API:

```bash
# Health check
curl http://localhost:8000/api/health

# Expected response:
# {"status":"healthy","timestamp":"...","service":"JarvisMD Automation Testing Tool","version":"1.0.0"}
```

### 5. Access Services

Once running, access these services:

- **API Documentation**: http://localhost:8000/api/docs
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Flower**: http://localhost:5555
- **Alertmanager**: http://localhost:9093

## Frontend Setup (Optional)

If you want to run the frontend separately (not in Docker):

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Frontend will be available at http://localhost:5173
```

## Verification Checklist

- [ ] Docker and Docker Compose installed
- [ ] `.env` file configured with OpenAI API key
- [ ] All Docker containers running (`docker-compose ps`)
- [ ] API health check returns "healthy"
- [ ] Can access Grafana at http://localhost:3000
- [ ] Can access API docs at http://localhost:8000/api/docs

## Troubleshooting

### Port Already in Use

If a port is already in use, either:
1. Stop the conflicting service
2. Change the port in `.env` and `docker-compose.yml`

### Docker Build Fails

```bash
# Clean Docker cache and rebuild
docker-compose build --no-cache

# Or remove old images
docker system prune -a
```

### Database Connection Issues

```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Verify database is ready
docker-compose exec postgres pg_isready -U medbench
```

### Services Not Starting

```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs api
docker-compose logs celery-worker
```

## Next Steps

- [Configure the system](configuration.md)
- [Run your first evaluation](first-evaluation.md)
- [Explore the user guides](../user-guides/)

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [OpenAI API Documentation](https://platform.openai.com/docs)

