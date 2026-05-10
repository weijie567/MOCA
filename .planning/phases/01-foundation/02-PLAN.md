---
phase: 1
plan_id: "02"
title: "Authentication System + RBAC"
wave: 1
depends_on: ["01"]
files_modified:
  - src/auth/__init__.py
  - src/auth/jwt.py
  - src/auth/permissions.py
  - src/api/__init__.py
  - src/api/main.py
  - src/api/deps.py
  - src/api/routers/__init__.py
  - src/api/routers/auth.py
  - src/api/schemas/__init__.py
  - src/api/schemas/auth.py
  - src/api/schemas/common.py
autonomous: true
requirements: [INFR-03]
---

# Plan 02: Authentication System + RBAC

<objective>
Implement JWT-based authentication with login flow, demo-token endpoint, get_current_user dependency, and role-based access control (4 fixed roles). Establish the unified response format and trace_id middleware.
</objective>

<tasks>

<task id="02-01">
<title>Create unified response schemas</title>
<read_first>
- src/config.py
- .planning/phases/01-foundation/01-CONTEXT.md (D-10: unified error format)
</read_first>
<action>
Create `src/api/__init__.py` (empty).
Create `src/api/schemas/__init__.py` (empty).
Create `src/api/schemas/common.py`:

```python
from pydantic import BaseModel
from typing import Any

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}

class ApiResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: ErrorDetail | None = None
    trace_id: str | None = None
```

Error codes as constants:
UNAUTHORIZED = "UNAUTHORIZED"
FORBIDDEN = "FORBIDDEN"
VALIDATION_ERROR = "VALIDATION_ERROR"
ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
REFUND_CASE_NOT_FOUND = "REFUND_CASE_NOT_FOUND"
TICKET_NOT_FOUND = "TICKET_NOT_FOUND"
POLICY_DOCUMENT_NOT_FOUND = "POLICY_DOCUMENT_NOT_FOUND"
TENANT_SCOPE_VIOLATION = "TENANT_SCOPE_VIOLATION"
INTERNAL_ERROR = "INTERNAL_ERROR"
</action>
<acceptance_criteria>
- src/api/schemas/common.py contains `class ErrorDetail(BaseModel)`
- src/api/schemas/common.py contains `class ApiResponse(BaseModel)`
- src/api/schemas/common.py contains `success: bool`
- src/api/schemas/common.py contains `trace_id: str`
- src/api/schemas/common.py contains `UNAUTHORIZED = "UNAUTHORIZED"`
- src/api/schemas/common.py contains `FORBIDDEN = "FORBIDDEN"`
- src/api/schemas/common.py contains `TENANT_SCOPE_VIOLATION`
</acceptance_criteria>
</task>

<task id="02-02">
<title>Create JWT utilities (create/decode token)</title>
<read_first>
- src/config.py
</read_first>
<action>
Create `src/auth/__init__.py` (empty).
Create `src/auth/jwt.py`:

- create_access_token(data: dict) -> str
  - payload: sub=user_id, username, role, tenant_id, exp=now+jwt_expire_minutes
  - encode with settings.jwt_secret, algorithm=settings.jwt_algorithm
- decode_access_token(token: str) -> dict
  - decode with settings.jwt_secret
  - raise on ExpiredSignatureError, InvalidTokenError
- verify_password(plain: str, hashed: str) -> bool
  - passlib CryptContext with bcrypt
- hash_password(password: str) -> str
  - passlib CryptContext with bcrypt
</action>
<acceptance_criteria>
- src/auth/jwt.py contains `def create_access_token`
- src/auth/jwt.py contains `def decode_access_token`
- src/auth/jwt.py contains `def verify_password`
- src/auth/jwt.py contains `def hash_password`
- src/auth/jwt.py contains `settings.jwt_secret`
- src/auth/jwt.py contains `settings.jwt_algorithm`
- src/auth/jwt.py contains `CryptContext`
</acceptance_criteria>
</task>

<task id="02-03">
<title>Create auth dependencies (get_current_user, require_roles)</title>
<read_first>
- src/auth/jwt.py
- src/db/models.py
- src/db/session.py
</read_first>
<action>
Create `src/auth/permissions.py`:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    # Decode token, query user by sub (user_id), verify is_active
    # Attach role from token payload to user object
    # Raise 401 if token invalid/expired or user not found/inactive

def require_roles(allowed_roles: list[str]):
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Insufficient permissions"})
        return user
    return role_checker
```

User object should carry: id, username, role, tenant_id, merchant_id (if merchant role).
</action>
<acceptance_criteria>
- src/auth/permissions.py contains `oauth2_scheme = OAuth2PasswordBearer`
- src/auth/permissions.py contains `async def get_current_user`
- src/auth/permissions.py contains `def require_roles`
- src/auth/permissions.py contains `allowed_roles`
- src/auth/permissions.py contains `status_code=403` or `HTTP_403_FORBIDDEN`
</acceptance_criteria>
</task>

<task id="02-04">
<title>Create auth router (login, me, demo-token)</title>
<read_first>
- src/auth/jwt.py
- src/auth/permissions.py
- src/api/schemas/common.py
</read_first>
<action>
Create `src/api/schemas/auth.py`:
- LoginRequest: username(str), password(str)
- TokenResponse: access_token(str), token_type(str = "bearer")
- UserResponse: id(str), username(str), role(str), tenant_id(str)
- DemoTokenRequest: username(str)

Create `src/api/routers/__init__.py` (empty).
Create `src/api/routers/auth.py`:

POST /api/v1/auth/login:
  - Query user by username, verify password
  - Return TokenResponse wrapped in ApiResponse
  - 401 if credentials invalid

GET /api/v1/auth/me:
  - Depends(get_current_user)
  - Return UserResponse wrapped in ApiResponse

POST /api/v1/auth/demo-token:
  - Check settings.enable_demo_auth is True, else 403
  - Accept username, look up user in DB — if not found, return 404
  - Create token from the real user's data (role, tenant_id from DB)
  - Return TokenResponse wrapped in ApiResponse
  - This ensures demo-token can only mint tokens for existing seeded users
</action>
<acceptance_criteria>
- src/api/routers/auth.py contains `@router.post` with path containing "login"
- src/api/routers/auth.py contains `@router.get` with path containing "me"
- src/api/routers/auth.py contains `demo-token` or `demo_token`
- src/api/routers/auth.py contains `settings.enable_demo_auth`
- src/api/schemas/auth.py contains `class LoginRequest`
- src/api/schemas/auth.py contains `class TokenResponse`
</acceptance_criteria>
</task>

<task id="02-05">
<title>Create FastAPI app with trace_id middleware and exception handlers</title>
<read_first>
- src/api/routers/auth.py
- src/api/schemas/common.py
- src/db/session.py
</read_first>
<action>
Create `src/api/main.py`:

- FastAPI app factory with title="MOCA API", version="0.1.0"
- Middleware: generate trace_id (uuid4) per request, store in request.state.trace_id
- Exception handlers:
  - HTTPException → ApiResponse(success=False, error=ErrorDetail(...), trace_id=...)
  - RequestValidationError → ApiResponse(success=False, error=ErrorDetail(code="VALIDATION_ERROR", ...), trace_id=...)
  - Generic Exception → ApiResponse(success=False, error=ErrorDetail(code="INTERNAL_ERROR", ...), trace_id=...)
- GET /health endpoint: check DB connectivity, return {"status": "healthy", "database": "connected"}
- Include auth router with prefix="/api/v1/auth"

Create `src/api/deps.py`:
- Re-export get_session from src.db.session
- Helper to extract trace_id from request
</action>
<acceptance_criteria>
- src/api/main.py contains `FastAPI(`
- src/api/main.py contains `trace_id`
- src/api/main.py contains `@app.get("/health")`
- src/api/main.py contains `include_router`
- src/api/main.py contains `RequestValidationError`
- src/api/main.py contains `ApiResponse`
- src/api/deps.py contains `get_session`
</acceptance_criteria>
</task>

</tasks>

<verification>
- `uv run fastapi dev src/api/main.py` starts without errors
- GET /health returns `{"success": true, "data": {"status": "healthy"}, "trace_id": "..."}`
- POST /api/v1/auth/login with valid credentials returns access_token
- POST /api/v1/auth/login with wrong password returns 401 with unified error format
- GET /api/v1/auth/me with valid token returns user info
- GET /api/v1/auth/me without token returns 401
- POST /api/v1/auth/demo-token works when ENABLE_DEMO_AUTH=true
- All error responses include trace_id
</verification>

<must_haves>
- Real login flow with hashed passwords (not pre-generated tokens)
- JWT contains sub, username, role, tenant_id, exp
- get_current_user dependency validates token and returns user
- require_roles dependency enforces role-based access
- All responses follow unified format with trace_id
- demo-token gated by ENABLE_DEMO_AUTH env var
</must_haves>

<threat_model>
| Threat | Severity | Mitigation |
|--------|----------|-----------|
| Brute force login | Medium | Phase 1 accepts risk; Phase 2+ adds rate limiting via Redis |
| JWT secret in env | Medium | Loaded from env var, not hardcoded; .env in .gitignore |
| Token theft (no refresh) | Low | Short expiry (60min default); demo context acceptable |
| Password in request body | Low | HTTPS in production; dev is localhost only |
| Timing attack on password verify | Low | passlib bcrypt has constant-time comparison |
</threat_model>
