# NL-to-SQL Agent

A self-correcting agent that turns natural-language questions into SQL, executes them, and automatically fixes its own mistakes when a query fails — built as a demonstration of agentic AI design, not just an LLM wrapper.

## The problem it solves

Most people who need data from a database don't know SQL and have to rely on someone else to write queries for them. This agent removes that bottleneck: ask a plain-English question, get real results back.

## What makes it "agentic"

A basic version would call an LLM once and hope the SQL is correct. This agent goes further:
1. **Schema-aware generation** — reads the database's actual table/column structure at runtime (via SQLite's `sqlite_master` + `PRAGMA`), so it works on any schema without code changes.
2. **Safe execution** — only allows `SELECT` statements, protecting against a hallucinated destructive query.
3. **Self-correction loop** — when a query fails, the exact error is fed back to the LLM along with the original question, and it gets up to 3 attempts to fix itself.
4. **Confidence scoring** — the LLM also reports how confident it is in each generated query, surfaced to the user as a heuristic signal for ambiguous questions.

## Tech stack

- **Backend:** Python, FastAPI
- **Database:** SQLite
- **LLM:** Google Gemini API
- **Frontend:** HTML/CSS/vanilla JavaScript

## Architecture
