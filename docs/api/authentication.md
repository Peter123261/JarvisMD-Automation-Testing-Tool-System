# API Authentication

Authentication and authorization for the MedBench Automation Testing Tool API.

## Current Status

**Development Mode**: No authentication required

The API currently runs without authentication for development purposes. All endpoints are publicly accessible.

## Production Authentication

For production deployments, implement one of the following:

### Option 1: API Keys

**Implementation:**
- Generate API keys for each client
- Store keys in database
- Validate key in middleware
- Rate limiting per key

**Example:**
```python
# middleware/auth.py
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    # Validate key against database
    if not is_valid_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key
```

### Option 2: OAuth2

**Implementation:**
- Use FastAPI's OAuth2 support
- JWT tokens for authentication
- Refresh token mechanism
- Role-based access control

**Example:**
```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    # Validate JWT token
    # Return user information
    pass
```

### Option 3: Basic Authentication

**Implementation:**
- Username/password authentication
- HTTP Basic Auth
- Session management

## Security Best Practices

### Environment Variables

Store sensitive credentials in environment variables:

```bash
# .env
API_SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret
```

### HTTPS

Always use HTTPS in production:
- TLS/SSL certificates
- Redirect HTTP to HTTPS
- Secure cookie settings

### CORS Configuration

Restrict CORS origins to known domains:

```python
CORS_ORIGINS = [
    "https://yourdomain.com",
    "https://app.yourdomain.com"
]
```

### Rate Limiting

Implement rate limiting to prevent abuse:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/test/start")
@limiter.limit("10/minute")
async def start_evaluation(...):
    pass
```

## API Key Management

### Generating Keys

```python
import secrets

def generate_api_key():
    return secrets.token_urlsafe(32)
```

### Storing Keys

Store keys securely:
- Hash keys in database
- Use environment variables for secrets
- Rotate keys regularly

### Key Validation

```python
async def validate_api_key(api_key: str):
    # Check key exists and is active
    # Check rate limits
    # Log usage
    return True
```

## Future Enhancements

Planned authentication features:
- [ ] API key authentication
- [ ] JWT token support
- [ ] Role-based access control
- [ ] Rate limiting
- [ ] Audit logging

## Next Steps

- [API Endpoints](endpoints.md)
- [Examples](examples.md)

