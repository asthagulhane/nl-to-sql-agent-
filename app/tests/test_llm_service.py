
import os
import sqlite3
import json
import time
from pathlib import Path

from groq import Groq
from dotenv import load_dotenv

from app.rag.retriever import get_relevant_schema

from app.app.governance import (
    enforce_row_limit,
    apply_authorizer,
)

from app.app.semantic_layer import build_semantic_context


# ---------------------------------------------------------
# Canonical database path
# ---------------------------------------------------------

DATABASE_PATH = str(
    Path(__file__).resolve().parents[1] / "sample.db"
)


# ---------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------

ENV_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".env",
    )
)

load_dotenv(ENV_PATH)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        f"GROQ_API_KEY was not found. Expected it in: {ENV_PATH}"
    )

client = Groq(api_key=GROQ_API_KEY)
