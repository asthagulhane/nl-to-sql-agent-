# NL-to-SQL Agent

A self-correcting agent that turns natural-language questions into SQL, executes them, and automatically fixes its own mistakes when a query fails — built as a demonstration of agentic AI design, not just an LLM wrapper.

## The problem it solves

Most people who need data from a database don't know SQL and have to rely on someone else to write queries for them. This agent removes that bottleneck: ask a plain-English question, get real results back.

## What makes it "agentic"

A basic version would call an LLM once and hope the SQL is correct. This agent goes further:

1. **RAG-based schema retrieval** — instead of sending the full database schema on every request, table schemas are embedded (via `sentence-transformers`) and indexed in FAISS. At query time, only the most relevant tables are retrieved and injected into the prompt, keeping requests smaller and more accurate as the schema grows.
2. **Safe execution** — only allows `SELECT` statements, protecting against a hallucinated destructive query.
3. **Self-correction loop** — when a query fails, the exact error is fed back to the LLM along with the original question, and it gets up to 3 attempts to fix itself.
4. **Confidence scoring** — the LLM also reports how confident it is in each generated query, surfaced to the user as a heuristic signal for ambiguous questions.
5. **Input validation** — empty or overly long questions are rejected before reaching the LLM, avoiding wasted API calls.

## Tech stack

- **Backend:** Python, FastAPI
- **Database:** SQLite
- **LLM:** Groq (Llama 3.3 70B)
- **RAG:** FAISS + sentence-transformers
- **Config:** pydantic-settings
- **Testing:** pytest
- **Containerization:** Docker
- **Deployment:** Azure App Service, CI/CD via GitHub Actions
- **Frontend:** HTML/CSS/vanilla JavaScript

## Architecture