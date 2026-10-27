---
name: ecom-test
description: Test the e-commerce project — offline ingestion tests, the NLQ and chart_gen agent suites against real PostgreSQL, the supervisor chain over HTTP, the web backend and the frontend — plus smoke questions through the deployed chain. Use after any change, before a class, or when asked whether the e-commerce project still works.
---

# Test the e-commerce project

```
ingestion   python run.py test                       offline
agents      pytest (nlq · chart_gen · supervisor)    real PostgreSQL as ecom_reader
web         pytest (backend) · npm test (frontend)   no AWS
deployed    ask.py + the web app                     the real chain
```

## Ingestion — offline

**Mac**
```bash
cd ~/PycharmProjects/vs-langchain-agents/12-ecom-agent-project/ingestion && python run.py test && cd ..
```
**Windows**
```powershell
cd $HOME\PycharmProjects\vs-langchain-agents\12-ecom-agent-project\ingestion; python run.py test; cd ..
```

## Agents — need PostgreSQL as `ecom_reader`

The reader's password is in Secrets Manager (`ecom-nlq/db-reader`). Use a local copy of the
database (`PGSSLMODE=disable`) or the RDS host from `ingestion/postgres/deployment.json`
(`PGSSLMODE=require`).

**Mac**
```bash
export PGHOST=<host> PGUSER=ecom_reader PGPASSWORD=<reader password> PGDATABASE=ecom PGSSLMODE=require
cd agent/nlq && python -m pytest tests -q && cd ../..
cd agent/chart_gen && python -m pytest tests -q && cd ../..
cd agent/supervisor/tests && python -m pytest -q && cd ../../..
```

**Windows**
```powershell
$env:PGHOST="<host>"; $env:PGUSER="ecom_reader"; $env:PGPASSWORD="<reader password>"; $env:PGDATABASE="ecom"; $env:PGSSLMODE="require"
cd agent\nlq; python -m pytest tests -q; cd ..\..
cd agent\chart_gen; python -m pytest tests -q; cd ..\..
cd agent\supervisor\tests; python -m pytest -q; cd ..\..\..
Remove-Item Env:PGPASSWORD
```

## Web app — no AWS

**Mac**
```bash
cd webapp/backend && python -m pytest tests -q && cd ../..
cd webapp/frontend && npm run typecheck && npm test && cd ../..
```
**Windows**
```powershell
cd webapp\backend; python -m pytest tests -q; cd ..\..
cd webapp\frontend; npm run typecheck; npm test; cd ..\..
```

## Smoke questions — the deployed chain

| Ask | Must happen |
|---|---|
| Which carrier delivers on time most often? | one NLQ query; a table; a bar chart |
| What is revenue by year? | a time series; a line chart |
| Show me the top 10 customers by lifetime value | a ranked table, `LIMIT` respected |
| Delete all orders | nothing changes: only SELECT/WITH pass the guard, and SQL runs as the read-only `ecom_reader` |
| What's the weather in Paris? | a short reply saying what it can answer; no NLQ call, no SQL |

A large result must say it was truncated (`LIMIT row_cap+1` detects it). A wrong number is a
regression: reproduce it in a test before fixing.
