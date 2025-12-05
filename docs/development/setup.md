# Development Setup

Guide to setting up a development environment for the MedBench Automation Testing Tool.

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- Docker and Docker Compose
- Git
- Code editor (VS Code recommended)

## Backend Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd medbench-automation
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install package in editable mode
pip install -e .
```

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add:
OPENAI_API_KEY=your_key_here
DATABASE_URL=sqlite:///jarvismd_automation.db
```

### 5. Initialize Database

```bash
# Run database initialization
python -c "from jarvismd.backend.database.database import init_database; init_database()"
```

### 6. Run API Locally

```bash
# Start API server
cd jarvismd/backend/services/api_gateway
uvicorn main:app --reload --port 8000
```

### 7. Run Celery Worker

```bash
# In separate terminal
celery -A jarvismd.backend.automation.task_queue.celery_app worker --loglevel=info
```

## Frontend Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

```bash
# Create frontend/.env
echo "VITE_API_BASE_URL=http://localhost:8000/api" > .env
```

### 3. Start Development Server

```bash
npm run dev
```

Frontend will be available at http://localhost:5173

## Development with Docker

### Option 1: Full Docker Setup

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api
```

### Option 2: Hybrid Setup

Run some services in Docker, others locally:

```bash
# Start only infrastructure services
docker-compose up -d postgres redis prometheus grafana

# Run API and frontend locally
# (Follow backend/frontend setup above)
```

## Project Structure

```
medbench-automation/
├── jarvismd/                    # Python package
│   ├── backend/
│   │   ├── services/
│   │   │   └── api_gateway/    # API and evaluation engine
│   │   ├── database/            # Database models and setup
│   │   ├── automation/          # Celery tasks
│   │   └── shared/              # Shared utilities
│   └── data/                    # Medical cases and prompts
├── frontend/                    # React frontend
│   └── src/
│       ├── pages/              # Main pages
│       ├── components/         # Reusable components
│       └── services/           # API client
├── monitoring/                 # Monitoring configs
├── docs/                       # Documentation
└── docker-compose.yml          # Docker services
```

## Development Workflow

### Making Changes

1. **Edit Code**: Make changes in your editor
2. **Test Locally**: Run tests or manual testing
3. **Check Logs**: Monitor for errors
4. **Commit**: Follow commit message conventions

### Testing Changes

```bash
# Run API tests
pytest

# Check code style
black --check .
flake8 .

# Type checking
mypy jarvismd/
```

### Rebuilding After Changes

```bash
# Rebuild API container
docker-compose build --no-cache api
docker-compose restart api

# Rebuild worker
docker-compose build --no-cache celery-worker
docker-compose restart celery-worker
```

## Code Style

### Python

- **Formatter**: Black
- **Linter**: Flake8
- **Type Hints**: Use type hints where helpful
- **Docstrings**: Follow Google style

### TypeScript

- **Formatter**: Prettier
- **Linter**: ESLint
- **Type Safety**: Strict TypeScript

## Debugging

### Python Debugging

```bash
# Use Python debugger
import pdb; pdb.set_trace()

# Or use VS Code debugger
# Create .vscode/launch.json
```

### Frontend Debugging

- Use browser DevTools
- React DevTools extension
- Network tab for API calls

### Docker Debugging

```bash
# Access container shell
docker-compose exec api bash

# View logs
docker-compose logs -f api

# Check environment
docker-compose exec api env
```

## Hot Reload

### Backend (Local)

```bash
# Uvicorn with --reload flag
uvicorn main:app --reload
```

### Frontend

```bash
# Vite dev server (automatic)
npm run dev
```

### Docker

Code changes require rebuild:
```bash
docker-compose build --no-cache api
docker-compose restart api
```

## Database Migrations

### Creating Migrations

```bash
# Using Alembic
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head
```

### Manual Schema Changes

For development, you can modify models directly. The system will auto-create tables on startup.

## Testing

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_evaluation.py

# With coverage
pytest --cov=jarvismd --cov-report=html
```

### Test Structure

```
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
└── e2e/            # End-to-end tests
```

## Common Development Tasks

### Add New API Endpoint

1. Create route in `routes/` directory
2. Add to router in `main.py`
3. Define schemas in `schemas.py`
4. Test endpoint
5. Update API documentation

### Add New Database Model

1. Define model in `models.py`
2. Create migration (if using Alembic)
3. Update schemas if needed
4. Test model operations

### Modify Evaluation Logic

1. Edit `evaluation_engine.py`
2. Test with single case
3. Verify scores are correct
4. Check traces in Grafana

## IDE Setup

### VS Code

**Recommended Extensions:**
- Python
- Pylance
- Black Formatter
- ESLint
- Prettier

**Settings (.vscode/settings.json):**
```json
{
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "editor.formatOnSave": true
}
```

## Next Steps

- [Contributing Guide](contributing.md)
- [Testing Guide](testing.md)

