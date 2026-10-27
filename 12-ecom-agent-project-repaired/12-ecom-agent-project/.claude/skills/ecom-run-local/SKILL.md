---
name: ecom-run-local
description: Run the e-commerce web app locally — FastAPI backend on :8000 storing in DynamoDB ecom-webapp, React frontend on :5173 — against the supervisor deployed in AgentCore, with streamed reasoning, tables and charts. Use when someone asks to run, start or try the e-commerce web app or its admin console.
---

# Run the e-commerce web app locally

```
browser :5173 ──/api──► Vite proxy ──► backend :8000 ──A2A message/stream (SigV4)──► ecom_supervisor (AWS)
                                          │  SSE to the browser: status · reasoning · token · artifact · done
                                          └──► DynamoDB ecom-webapp  users · conversations · messages · feedback
```

**Before:** the agents are deployed (`ecom-deploy-agents`) and `ask.py` answers.

## 1. Backend — first terminal tab

**Mac**
```bash
cd ~/PycharmProjects/vs-langchain-agents/12-ecom-agent-project/webapp/backend
pip install -r requirements.txt
cp .env.example .env
python run.py
```

**Windows**
```powershell
cd $HOME\PycharmProjects\vs-langchain-agents\12-ecom-agent-project\webapp\backend
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

In `.env`, set (only the first time):

| Setting | Value |
|---|---|
| `SUPERVISOR_ARN` | `runtime_arn` from `agent/supervisor/deployment.json` |
| `SESSION_SECRET` | any long random string |
| `PINECONE_API_KEY`, `OPENAI_API_KEY` | for the admin console's knowledge-base browser |

The first start creates the DynamoDB table `ecom-webapp` if it is missing. API docs:
http://localhost:8000/api/docs

## 2. Frontend — second terminal tab

**Mac**
```bash
cd ~/PycharmProjects/vs-langchain-agents/12-ecom-agent-project/webapp/frontend
npm install --legacy-peer-deps
npm run dev
```

**Windows**
```powershell
cd $HOME\PycharmProjects\vs-langchain-agents\12-ecom-agent-project\webapp\frontend
npm install --legacy-peer-deps
npm run dev
```

Open http://localhost:5173. `--legacy-peer-deps` is required: plain `npm install` crashes on
this dependency tree with `reading 'edgesOut'`.

## What each answer shows

Summary · Reasoning (live while it runs) · chart(s) · table · sources · 👍 👎 with a comment.
Every user is an admin by default (`ADMIN_USERS` unset): `/admin` shows AgentOps (usage,
CloudWatch traces), feedback and the knowledge-base browser. Set `ADMIN_USERS=a,b` to limit it.

## Try a turn without the frontend (Mac)

```bash
curl -s -c /tmp/ecom.cookies -H 'Content-Type: application/json' localhost:8000/api/v1/auth/login \
  -d '{"username":"prudhvi","password":"a-long-password","first_name":"Prudhvi","last_name":"A"}'
curl -N -b /tmp/ecom.cookies -H 'Content-Type: application/json' localhost:8000/api/v1/chat/message \
  -d '{"text":"Which carrier delivers on time most often?"}'
```
