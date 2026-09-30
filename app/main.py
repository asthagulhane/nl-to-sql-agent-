import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.app.llm_service import generate_and_run
from app.app.governance import (
    mask_results,
    log_audit_entry,
    normalize_role,
)


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="QueryMind - Governed Analytics Agent",
    description=(
        "Natural-language-to-SQL analytics API with "
        "role-based access control, masking, row limits, "
        "audit logging, and self-correcting SQL generation."
    ),
    version="1.1.0",
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

FRONTEND_PATH = os.path.join(
    BASE_DIR,
    "app",
    "index.html",
)


# ---------------------------------------------------------
# Request model
# ---------------------------------------------------------

class QuestionRequest(BaseModel):
    question: str
    role: str = "viewer"


# ---------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------

@app.get("/")
def read_root():
    return {
        "message": "QueryMind NL-to-SQL Agent is alive!",
        "version": "1.1.0",
    }


# ---------------------------------------------------------
# Frontend
# ---------------------------------------------------------

@app.get("/ui")
def serve_frontend():
    return FileResponse(
        FRONTEND_PATH
    )


# ---------------------------------------------------------
# NL-to-SQL endpoint
# ---------------------------------------------------------

@app.post("/query")
def query(request: QuestionRequest):
    """
    Convert a natural-language question into SQL and
    execute it through the governance pipeline.

    Governance includes:

    - SELECT-only enforcement
    - automatic row limits
    - SQLite authorizer-based RBAC
    - sensitive-column masking
    - audit logging
    """

    # -----------------------------------------------------
    # Normalize role
    # -----------------------------------------------------

    role = normalize_role(
        request.role
    )

    # -----------------------------------------------------
    # Generate and execute SQL
    #
    # IMPORTANT:
    # The role is passed into generate_and_run().
    #
    # generate_and_run()
    #       ↓
    # execute_query()
    #       ↓
    # apply_authorizer()
    #       ↓
    # SQLite
    # -----------------------------------------------------

    result = generate_and_run(
        request.question,
        role=role,
    )

    # -----------------------------------------------------
    # Defense-in-depth result masking
    # -----------------------------------------------------

    if result.get("results") is not None:
        result["results"] = mask_results(
            result["results"],
            role,
        )

    # -----------------------------------------------------
    # Audit logging
    # -----------------------------------------------------

    results = result.get("results")

    row_count = (
        len(results)
        if results is not None
        else 0
    )

    success = (
        result.get("final_sql")
        is not None
        and result.get("error") is None
    )

    log_audit_entry(
        role=role,
        question=request.question,
        sql=result.get("final_sql"),
        row_count=row_count,
        success=success,
        error=result.get("error"),
    )

    # -----------------------------------------------------
    # API response
    # -----------------------------------------------------

    return result