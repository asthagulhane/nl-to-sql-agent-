# QueryMind — Governed Analytics Agent

QueryMind is a FastAPI application that converts natural-language analytics questions into bounded, read-only SQL. Generated SQL is treated as an untrusted proposal: the application authenticates the caller, applies role-aware controls, validates the query, executes it against a read-only SQLite connection, limits returned rows, masks restricted values, and records audit events.

> **Status:** software-engineering portfolio project. The current implementation uses SQLite and process-local rate limiting; it is not yet a multi-tenant production service.

## Request lifecycle

1. Authenticate the caller using server-configured API keys and map the key to a role.
2. Validate the question and apply request rate limits.
3. Retrieve relevant schema context and approved semantic definitions.
4. Generate a SQLite read query through the configured Groq model.
5. Validate the SQL candidate and apply role-aware database authorization.
6. Execute through a read-only connection with a timeout and bounded result fetch.
7. Mask restricted values, return structured results, and append an audit event.

## Engineering capabilities

- FastAPI API and browser UI
- API-key authentication with viewer / analyst / admin role mapping
- Per-process request rate limiting
- Read-only SQLite connections and database authorizer
- SQL candidate validation and bounded execution
- Query timeout and maximum result-row controls
- Role-aware result masking
- FAISS + sentence-transformers schema retrieval (lazy-loaded)
- LLM-assisted SQL correction for eligible execution failures
- JSONL audit trail and security-event feed
- Pytest API and security tests
- GitHub Actions workflow and Docker packaging

## Architecture

```text
Browser / API client
        |
        v
FastAPI routes
        |
        +--> API-key authentication --> Role mapping
        +--> Request validation + rate limiting
        |
        v
Query orchestration
        |
        +--> Schema retrieval (FAISS / embeddings)
        +--> Semantic definitions
        +--> Groq SQL generation / correction
        |
        v
SQL validation + governance
        |
        +--> Read-only SQLite connection
        +--> Database authorizer
        +--> Query timeout + row cap
        |
        v
Result masking --> JSON response
        |
        +--> Audit log / security events
```

## Technology

- Python 3.11, FastAPI, SQLite
- Groq model API
- FAISS, sentence-transformers
- HTML, CSS and vanilla JavaScript
- pytest, GitHub Actions, Docker

## Run locally

Run commands from the repository root.

1. Create the local environment file:

   ```powershell
   Copy-Item app/.env.example app/.env
   ```

2. Edit `app/.env` with your Groq API key and separate long random API keys for the roles you want to use. Never commit or share this file.

3. Install dependencies:

   ```powershell
   python -m pip install -r app/requirements.txt
   ```

4. Run tests:

   ```powershell
   python -m pytest -q app/tests
   ```

5. Start the API:

   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --env-file app/.env
   ```

6. Open [http://127.0.0.1:8010/ui](http://127.0.0.1:8010/ui). The liveness endpoint is [http://127.0.0.1:8010/health](http://127.0.0.1:8010/health).

### Example PowerShell API request

```powershell
$headers = @{ "X-API-Key" = "YOUR_VIEWER_API_KEY" }
$body = @{ question = "Show employee names" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/query -Headers $headers -ContentType "application/json" -Body $body
```

## Docker

Build and run:

```bash
docker build -t querymind .
docker run --rm -p 8000:8000 --env-file app/.env querymind
```

The image runs as a non-root user. Review the Dockerfile and [SECURITY.md](SECURITY.md) before exposing the service.

## Verification

Run `python -m pytest -q app/tests` locally. GitHub Actions is intended to run the same suite on pushes and pull requests. Passing tests do not, by themselves, establish production readiness or load capacity.

## Security boundaries and future work

See [SECURITY.md](SECURITY.md). Before production use, the project needs deployment-grade secret management, HTTPS, shared rate limiting across workers, persistent/shared security-event storage, monitoring, backup and recovery, and load testing. The sample database and local configuration are for development and demonstration.
