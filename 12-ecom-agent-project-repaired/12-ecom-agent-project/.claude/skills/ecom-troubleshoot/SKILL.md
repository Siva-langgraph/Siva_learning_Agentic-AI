---
name: ecom-troubleshoot
description: Diagnose and fix errors in the e-commerce project — ingestion and RDS problems, Pinecone publishing, agent deploy failures, IAM propagation, missing deployment.json, web app sign-in or npm failures. Use whenever an ingestion command, deploy, ask.py, the agents or the web app fails, or someone pastes an error or traceback.
---

# Troubleshoot the e-commerce project

```
1 read the WHOLE error — the last line names the cause, the frames name the file
2 match it in the table below
3 check you are in the right folder and the new code is what is running
4 fix the cause, run the SAME command again — every deploy is safe to re-run
```

## Is the new code really running?

Every zip holds paths from the project root (`agent/nlq/...`, `webapp/backend/...`) and must be
unzipped in `12-ecom-agent-project`. A `deploy.py` copied into another folder deploys the wrong
agent. Traceback line numbers must match the file on disk.

## Ingestion

| You see | Cause | Fix |
|---|---|---|
| `missing packages for run.py ...` (e.g. duckdb) | environment lacks a package | `(.venv)` in the prompt, then `pip install -r requirements.txt` |
| `can't open file '...run.py'` | not in `ingestion/` | `cd ingestion` |
| `SyntaxError` on `python run.py ...` | typed in PyCharm's Python Console | use the Terminal tool window |
| `CERTIFICATE_VERIFY_FAILED` (macOS) | python.org Python without certificates | current `deploy.py` brings its own; or run "Install Certificates.command" |
| `cannot connect to Postgres ... timeout` | your IP changed (Wi-Fi, VPN) | `python run.py deploy` again — it adds the new IP |
| `ResourceNotFoundException` for the secret | a secret id that is not the full ARN | use `secret_arn` from `postgres/deployment.json` |
| knowledge-base workbook not found | `kb_feed/kb_feed_ecom.xlsx` missing | `python run.py prepare` builds it |
| `?` instead of `✓ ✗` / `UnicodeEncodeError` (Windows) | console code page | cosmetic; the current scripts force UTF-8 |
| `running scripts is disabled on this system` (Windows) | execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

## Agents

| You see | Cause | Fix |
|---|---|---|
| `Docker is not running` | building locally without Docker | start Docker Desktop, or deploy with `--image` |
| `Role validation failed` / `Access denied while validating ECR URI` / Lambda `cannot be assumed` | IAM propagation | retried automatically; if it persists, run the same deploy again |
| NLQ: `deployment.json missing` | ingestion's `postgres/deployment.json` absent | the NLQ deploy looks the RDS instance up in AWS; if none exists, run `ecom-ingest` |
| supervisor deploy cannot find nlq / chart_gen | they were not deployed, or not from this folder | deploy nlq and chart_gen first, from their folders |
| an answer shows a truncated table without saying so | old guard | current guards fetch `LIMIT row_cap+1` to detect truncation — redeploy NLQ |
| `image ... not found on Docker Hub` / `no linux/arm64 image` | wrong name, private repo, or wrong platform | check the name; repo public; republish with `publish_images.py` |

## Web app

| You see | Cause | Fix |
|---|---|---|
| first sign-in hangs, then 401/404 | old backend creating the table on the first request | current backend opens the store at startup |
| `npm ERR! Cannot read properties of null (reading 'edgesOut')` | npm 10 peer resolution | `npm install --legacy-peer-deps` |
| Vitest / Vite version conflict | mismatched majors | use the committed `package.json` / `package-lock.json` (Vite 6) |
| answers fail: no supervisor | `SUPERVISOR_ARN` missing in `webapp/backend/.env` | copy `runtime_arn` from `agent/supervisor/deployment.json` |
| `/admin` not visible | `ADMIN_USERS` set to a list without you | unset it (everyone is admin) or add your username |

## Where the logs are

| What | Where |
|---|---|
| an agent | CloudWatch Logs `/aws/bedrock-agentcore/runtimes/<runtime>-DEFAULT` |
| traces | CloudWatch › GenAI Observability; the admin console's AgentOps links to each |
| the SQL Lambda | CloudWatch Logs, the NLQ tools Lambda's log group |
| the local backend | the terminal running `python run.py` |

## Security

If a password or key was pasted into a chat, a ticket or a file, rotate it: the database
password via `ecom-ingest` ("Rotate"), API keys at their provider.
