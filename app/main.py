import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.app.llm_service import generate_and_run
from app.app.governance import mask_results, log_audit_entry


app = FastAPI(
    title="NL-to-SQL Agent",
    description="Natural language to SQL API with governance and auditing",
    version="1.0.0",
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FRONTEND_PATH = os.path.join(
    BASE_DIR,
    "app",
    "index.html"
)


# ---------------------------------------------------------
# Request model
# ---------------------------------------------------------

class QuestionRequest(BaseModel):
    question: str
    role: str = "viewer"


# ---------------------------------------------------------
# Health / root endpoint
# ---------------------------------------------------------

@app.get("/")
def read_root():
    return {
        "message": "NL-to-SQL Agent is alive!"
    }


# ---------------------------------------------------------
# Frontend
# ---------------------------------------------------------

@app.get("/ui")
def serve_frontend():
    return FileResponse(FRONTEND_PATH)


# ---------------------------------------------------------
# NL-to-SQL endpoint
# ---------------------------------------------------------

@app.post("/query")
def query(request: QuestionRequest):
    """
    Convert a natural-language question into SQL,
    execute it, apply governance rules, mask results
    according to the user's role, and record an
    audit entry.
    """

    result = generate_and_run(
        request.question
    )

    # Apply role-based masking to successful results.
    if result.get("results") is not None:
        result["results"] = mask_results(
            result["results"],
            request.role
        )

    # Record every request in the audit log.
    log_audit_entry(
        role=request.role,
        question=request.question,
        sql=result.get("final_sql"),
        row_count=(
            len(result["results"])
            if result.get("results")
            else 0
        ),
        success=(
            result.get("final_sql")
            is not None
        ),
        error=result.get("error"),
    )

    return result