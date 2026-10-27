# Commerce Insights Agent — real-time NLQ reference project

A separate, runnable project inspired by the original NLQ architecture. FastAPI exposes normal and SSE-streaming endpoints. An OpenAI tool-calling agent selects from a narrow set of read-only analytics tools. Tool code contains the SQL; the model never supplies arbitrary SQL.

## Architecture

```text
Browser / API client -> FastAPI + API-key guard -> bounded tool-calling agent
                                                   | allowlisted tool + JSON args
                                                   v
                                  fixed analytics queries (no model-generated SQL)
                                                   v
                                SQLite local demo OR PostgreSQL live data
                                                   v
                                tool results -> model summary -> response / SSE
```

## Run on Windows / PyCharm

Requires Python 3.11+, an OpenAI API key for model-backed questions, and PostgreSQL for shared live data. SQLite is only the local demo fallback.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `OPENAI_API_KEY`. For PostgreSQL, set `DATABASE_URL=postgresql://...`; otherwise the default SQLite database is local-only. Then run:

```powershell
python -m app.seed_demo
python -m uvicorn app.main:app --reload --port 8000
```

Health: `http://127.0.0.1:8000/health`; API docs: `http://127.0.0.1:8000/docs`.

```powershell
$body = @{ question = 'Show total sales by status' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/chat -ContentType 'application/json' -Body $body
```

For production, configure `APP_ENV=production`, `APP_API_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`, and `ALLOWED_ORIGINS` in a secret store. Place behind HTTPS ingress/API Gateway, add identity-provider authentication, rate limits, request quotas, logging/metrics, and use a database account with SELECT-only grants. The included Docker Compose is a local/staging convenience, not an AWS deployment. No cloud resources have been provisioned by creating this archive.
