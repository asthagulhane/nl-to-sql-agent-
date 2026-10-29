
import os
import json
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Load the project-root .env before importing modules that read API keys.
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

from app.app.llm_service import generate_and_run
from app.app.governance import mask_results, log_audit_entry, AUDIT_LOG_PATH
from app.app.security import role_for_api_key, enforce_rate_limit


app = FastAPI(
    title="QueryMind - Governed Analytics Agent",
    description=(
        "Natural-language-to-SQL analytics API with "
        "role-based access control, masking, row limits, "
        "audit logging, and self-correcting SQL generation."
    ),
    version="1.1.0",
)

FRONTEND_PATH = BASE_DIR / "app" / "index.html"


class QuestionRequest(BaseModel):
    question: str

    class Config:
        str_strip_whitespace = True
        extra = "ignore"


@app.get("/")
def read_root():
    return {
        "message": "QueryMind NL-to-SQL Agent is alive!",
        "version": "1.1.0",
    }


@app.get("/ui")
def serve_frontend():
    if not FRONTEND_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail="QueryMind frontend file was not found.",
        )
    return FileResponse(str(FRONTEND_PATH))


@app.post("/query")
def query(
    request: QuestionRequest,
    http_request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    enforce_rate_limit(http_request)
    role = role_for_api_key(x_api_key)

    question = request.question.strip()

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

    result = generate_and_run(question, role=role)

    if result.get("results") is not None:
        result["results"] = mask_results(result["results"], role)

    results = result.get("results")
    row_count = len(results) if results is not None else 0

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


@app.get("/api/audit")
def read_audit(
    limit: int = Query(default=50, ge=1, le=200),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Return recent audit events to authenticated administrators only."""
    role = role_for_api_key(x_api_key)

    if role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access is required to view audit events.",
        )

    audit_path = Path(AUDIT_LOG_PATH)

    if not audit_path.is_file():
        return {"events": [], "count": 0}

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
