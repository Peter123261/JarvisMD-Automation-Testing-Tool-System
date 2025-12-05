# Testing Guide

Testing strategies and practices for the MedBench Automation Testing Tool.

## Testing Philosophy

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows
- **Manual Testing**: Verify UI and user experience

## Running Tests

### Python Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_evaluation_engine.py

# Specific test
pytest tests/test_evaluation_engine.py::test_single_case_evaluation

# With coverage
pytest --cov=jarvismd --cov-report=html

# Verbose output
pytest -v
```

### Frontend Tests

```bash
cd frontend

# Run tests
npm test

# With coverage
npm test -- --coverage
```

## Test Structure

### Backend Tests

```
tests/
├── unit/
│   ├── test_evaluation_engine.py
│   ├── test_prompt_parser.py
│   └── test_database.py
├── integration/
│   ├── test_api_endpoints.py
│   └── test_celery_tasks.py
└── fixtures/
    └── sample_cases.py
```

### Frontend Tests

```
frontend/src/
├── __tests__/
│   ├── pages/
│   └── components/
└── test-utils/
```

## Writing Tests

### Unit Test Example

```python
import pytest
from jarvismd.backend.services.api_gateway.evaluation_engine import EvaluationEngine

def test_evaluate_single_case():
    """Test single case evaluation"""
    engine = EvaluationEngine()
    
    result = engine.evaluate_single_case(
        summary="Patient presents with headache",
        recommendation="Consider migraine"
    )
    
    assert result['success'] == True
    assert 'overall_score' in result
    assert result['overall_score'] >= 0
    assert result['overall_score'] <= 100
```

### Integration Test Example

```python
from fastapi.testclient import TestClient
from jarvismd.backend.services.api_gateway.main import app

client = TestClient(app)

def test_start_evaluation():
    """Test starting an evaluation via API"""
    response = client.post(
        "/api/test/start",
        json={
            "benchmark_name": "appraise_v2",
            "num_cases": 1
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "running"
```

### Frontend Test Example

```typescript
import { render, screen } from '@testing-library/react';
import { TestRunner } from '../pages/TestRunner';

test('renders test runner form', () => {
  render(<TestRunner />);
  expect(screen.getByText('Start Evaluation')).toBeInTheDocument();
});
```

## Test Fixtures

### Sample Data

```python
# tests/fixtures/sample_cases.py
SAMPLE_CASE = {
    "case_id": "test-case-1",
    "summary": "Patient presents with symptoms...",
    "recommendation": "Consider diagnosis and treatment..."
}
```

### Database Fixtures

```python
@pytest.fixture
def db_session():
    """Create test database session"""
    # Setup test database
    # Yield session
    # Teardown
    pass
```

## Mocking

### Mock External APIs

```python
from unittest.mock import patch, MagicMock

@patch('openai.ChatCompletion.create')
def test_evaluation_with_mock(mock_openai):
    """Test evaluation with mocked OpenAI API"""
    mock_openai.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{"score": 85}'))]
    )
    
    # Test evaluation
    result = evaluate_case(...)
    assert result['overall_score'] == 85
```

### Mock Database

```python
from unittest.mock import Mock

@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db
```

## Test Coverage

### Coverage Goals

- **Overall**: >80%
- **Critical Paths**: >90%
- **Utilities**: >70%

### View Coverage

```bash
# Generate HTML report
pytest --cov=jarvismd --cov-report=html

# Open report
open htmlcov/index.html
```

## Continuous Integration

### GitHub Actions (Example)

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements.txt
      - run: pytest --cov
```

## Best Practices

1. **Test Early**: Write tests alongside code
2. **Test Edge Cases**: Boundary conditions, errors
3. **Keep Tests Fast**: Mock slow operations
4. **Isolate Tests**: No dependencies between tests
5. **Clear Names**: Descriptive test names
6. **One Assertion**: Focus each test on one thing

## Next Steps

- [Development Setup](setup.md)
- [Contributing Guide](contributing.md)

