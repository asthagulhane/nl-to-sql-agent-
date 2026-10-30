
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------
# Environment and application imports
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

# Load environment variables before importing modules that use API keys.
load_dotenv(PROJECT_ROOT / ".env", override=False)

from app.app.llm_service import generate_and_run
from app.app.governance import (
    mask_results,
    log_audit_entry,
    AUDIT_LOG_PATH,
)
from app.app.request_router import classify_request
from app.app.security import (
    role_for_api_key,
    enforce_rate_limit,
    rate_limiter,
    security_events,
)


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="QueryMind - Governed Analytics Agent",
    description=(
        "Natural-language-to-SQL analytics API with API-key "
        "authentication, request routing, role-based access control, "
        "masking, row limits, audit logging, and self-correcting SQL."
    ),
    version="1.2.0",
)

FRONTEND_PATH = BASE_DIR / "app" / "index.html"


# ---------------------------------------------------------
# Request model
# ---------------------------------------------------------

class QuestionRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="ignore",
    )

    question: str


# ---------------------------------------------------------
# Health and frontend endpoints
# ---------------------------------------------------------

@app.get("/")
def read_root():
    return {
        "message": "QueryMind NL-to-SQL Agent is alive!",
        "version": "1.2.0",
    }


@app.get("/ui")
def serve_frontend():
    if not FRONTEND_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail="QueryMind frontend file was not found.",
        )

    return FileResponse(str(FRONTEND_PATH))


# ---------------------------------------------------------
# Authenticated governance endpoints
# ---------------------------------------------------------

@app.get("/api/access-controls")
def access_controls(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Return the authenticated role and effective server-side controls."""
    role = role_for_api_key(x_api_key)
    permissions = {
        "viewer": ["Run permitted read-only queries", "View masked results"],
        "analyst": ["Run permitted read-only queries", "View analytics results"],
        "admin": ["Run permitted read-only queries", "View audit and security events", "Inspect access controls"],
    }
    return {
        "authenticated": True,
        "current_role": role,
        "role": role,
        "authentication": "API key",
        "role_assignment": "Server-side",
        "database_access": "Read-only SQLite connection",
        "query_only": True,
        "maximum_rows": 100,
        "rate_limit_per_minute": rate_limiter.limit,
        "rate_limit_window_seconds": rate_limiter.window_seconds,
        "permissions": permissions.get(role, permissions["viewer"]),
        "available_roles": ["admin", "analyst", "viewer"],
    }


@app.get("/api/security-events")
def read_security_events(
    limit: int = Query(default=50, ge=1, le=200),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Return recent in-memory security events to administrators."""
    role = role_for_api_key(x_api_key)
    if role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access is required to view security events.",
        )
    events = security_events.recent(limit)
    return {"events": events, "count": len(events)}


# ---------------------------------------------------------
# Query endpoint
# ---------------------------------------------------------

@app.post("/query")
def query(
    request: QuestionRequest,
    http_request: Request,
    x_api_key: str | None = Header(
        default=None,
        alias="X-API-Key",
    ),
):
    """Authenticate, classify, execute, mask, and audit a query."""

    # 1. Apply rate limiting.
    enforce_rate_limit(http_request)

    # 2. Derive the role from server-configured API keys.
    role = role_for_api_key(x_api_key)

    question = request.question.strip()

    # 3. Validate the question before calling the LLM.
    if not question:
        raise HTTPException(
            status_code=422,
            detail="Question must not be empty.",
        )

    if len(question) > 1000:
        raise HTTPException(
            status_code=413,
            detail="Question is too long (maximum 1000 characters).",
        )

    # 4. Classify the request before generating SQL.
    classification = classify_request(question)

    if not classification.get("allowed", False):
        error_message = classification.get(
            "reason",
            "This request is not supported.",
        )
        category = classification.get("category", "unsupported")

        log_audit_entry(
            role=role,
            question=question,
            sql=None,
            row_count=0,
            success=False,
            error=error_message,
        )

        status_code = 422 if category == "invalid" else 400

        raise HTTPException(
            status_code=status_code,
            detail={
                "category": category,
                "message": error_message,
            },
        )

    # 5. Generate and execute SQL through the existing pipeline.
    result = generate_and_run(
        question,
        role=role,
    )

    # 6. Apply defense-in-depth result masking.
    if result.get("results") is not None:
        result["results"] = mask_results(
            result["results"],
            role,
        )

    # 7. Audit the query outcome.
    results = result.get("results")
    row_count = (
        len(results)
        if results is not None
        else result.get("row_count", 0)
    )

    success = (
        result.get("final_sql") is not None
        and result.get("error") is None
    )

    log_audit_entry(
        role=role,
        question=question,
        sql=result.get("final_sql"),
        row_count=row_count,
        success=success,
        error=result.get("error"),
    )

    return result


# ---------------------------------------------------------
# Administrator-only audit endpoint
# ---------------------------------------------------------

@app.get("/api/audit")
def read_audit(
    limit: int = Query(default=50, ge=1, le=200),
    x_api_key: str | None = Header(
        default=None,
        alias="X-API-Key",
    ),
):
    """Return recent audit events to authenticated administrators."""

    role = role_for_api_key(x_api_key)

    if role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access is required to view audit events.",
        )

    audit_path = Path(AUDIT_LOG_PATH)

    if not audit_path.is_file():
        return {
            "events": [],
            "count": 0,
        }

    events = []

    with audit_path.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                event = json.loads(line)

                if isinstance(event, dict):
                    events.append(event)

            except (json.JSONDecodeError, TypeError):
                continue

    recent = list(reversed(events[-limit:]))

    return {
        "events": recent,
        "count": len(recent),
    }
