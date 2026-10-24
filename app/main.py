
import os

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from app.llm_service import generate_and_run
from app.governance import mask_results, log_audit_entry
from app.request_router import classify_request
from app.security import role_for_api_key, enforce_rate_limit


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="QueryMind - Governed Analytics Agent",
    description=(
        "Natural-language-to-SQL analytics API with "
        "API-key authentication, request routing, role-based "
        "access control, masking, row limits, audit logging, "
        "and self-correcting SQL generation."
    ),
    version="1.2.0",
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FRONTEND_PATH = os.path.join(
    BASE_DIR,
    "app",
    "index.html",
)


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
# Health endpoint
# ---------------------------------------------------------

@app.get("/")
def read_root():
    return {
        "message": "QueryMind NL-to-SQL Agent is alive!",
        "version": "1.2.0",
    }


# ---------------------------------------------------------
# Frontend
# ---------------------------------------------------------

@app.get("/ui")
def serve_frontend():
    if not os.path.isfile(FRONTEND_PATH):
        raise HTTPException(
            status_code=404,
            detail="Frontend file not found.",
        )

    return FileResponse(FRONTEND_PATH)


# ---------------------------------------------------------
# NL-to-SQL endpoint
# ---------------------------------------------------------

@app.post("/query")
def query(
    request: QuestionRequest,
    http_request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    Authenticate the caller, classify the request, and only then
    invoke the NL-to-SQL pipeline.

    Roles come from server-configured API keys, not request JSON.
    """

    # 1. Apply rate limiting.
    enforce_rate_limit(http_request)

    # 2. Derive the role from the API key.
    role = role_for_api_key(x_api_key)

    question = request.question

    # 3. Reject empty or unrelated questions before calling the LLM.
    classification = classify_request(question)

    if not classification["allowed"]:
        error_message = classification["reason"]

        log_audit_entry(
            role=role,
            question=question,
            sql=None,
            row_count=0,
            success=False,
            error=error_message,
        )

        status_code = (
            422 if classification["category"] == "invalid" else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail={
                "category": classification["category"],
                "message": error_message,
            },
        )

    # 4. Generate and execute SQL through the existing pipeline.
    result = generate_and_run(
        question,
        role=role,
    )

    # 5. Apply defense-in-depth result masking.
    if result.get("results") is not None:
        result["results"] = mask_results(
            result["results"],
            role,
        )

    # 6. Audit the result.
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

    # 7. Return the existing pipeline response.
    return result
