# E-commerce NLQ Agentic AI — repaired source project

This is a repaired copy of the supplied project. It contains data ingestion, PostgreSQL/Pinecone grounding, three A2A agents (NLQ, chart generation, supervisor), and a React/FastAPI web application.

## Architecture

```text
CSV -> clean/validate -> PostgreSQL (business facts)
                    \-> knowledge feed -> Pinecone (schema/glossary/examples)
Browser -> FastAPI/SSE -> Supervisor -> NLQ agent -> SQL guard -> read-only SQL gateway -> PostgreSQL
                                  \-> chart agent -> sanitized chart artifact -> Browser
```

## Windows / PyCharm setup

The agent packages declare Python >=3.12. From the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

For data preparation:

```powershell
cd ingestion
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python run.py prepare
python run.py test
```

Put your source CSV files in `ingestion/data/raw/`. The archive does not include business CSVs; `prepare` requires them and stops if they are absent. Do not load data into a database until validation passes.

Install each agent package before its tests, e.g.:

```powershell
cd ..\agent\nlq\agent_code
python -m pip install -e .
cd ..
python -m pytest tests -q
```

Repeat for `chart_gen` and `supervisor`. For the backend, install `webapp/backend/requirements.txt`. For the frontend, run `npm ci`, `npm test`, and `npm run build` inside `webapp/frontend`.

## Static check

From the root run `python scripts/project_doctor.py`. It checks expected files and parses Python syntax; it does not verify live AWS/RDS/Pinecone/model access.

## Production cautions

- Never commit `.env`, API keys, database passwords, or AWS credentials.
- Use IAM roles and Secrets Manager in AWS; use a read-only PostgreSQL role for NLQ execution.
- Keep SQL validation, statement timeouts, and row limits server-side.
- Use TLS, private networking, authentication, request limits, logs/metrics, alarms, backups, and a staging smoke test before production traffic.
- Deployment scripts can create billable resources. Check the AWS account and region before running them.
- Set `NLQ_MODEL`, `CHART_MODEL`, and `SUPERVISOR_MODEL` to model identifiers enabled for your account/provider.

## Verification status

Python syntax and project structure can be checked offline. Full tests require the dependencies in each service's `pyproject.toml` / `requirements.txt`, plus any fixture data. Live cloud integration tests require your credentials and deployed resources.
