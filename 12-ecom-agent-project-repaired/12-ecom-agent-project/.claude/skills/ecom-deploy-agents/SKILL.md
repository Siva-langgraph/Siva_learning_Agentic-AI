---
name: ecom-deploy-agents
description: Deploy the e-commerce agents to AWS Bedrock AgentCore in the required order — NLQ, chart_gen, then the supervisor — from prebuilt Docker Hub images or a local Docker build, and smoke-test the chain with ask.py. Use when deploying or redeploying the e-commerce agents.
---

# Deploy the e-commerce agents

```
ingestion done ─► nlq        reader user · VPC Lambda + Gateway · secrets · runtime ecom_nlq
                  chart_gen  runtime ecom_chart_gen
                  supervisor reads nlq/ and chart_gen/ deployment.json ─► runtime ecom_supervisor
                  ask.py     one question through the whole chain
```

**Before:** `ecom-ingest` is done (`ingestion/postgres/deployment.json` exists, Pinecone
`ecom-kb` is published) and `ingestion/.env` has `OPENAI_API_KEY` and `PINECONE_API_KEY`.

## Install once

**Mac**
```bash
cd ~/PycharmProjects/vs-langchain-agents/12-ecom-agent-project/agent/nlq
pip install -r ../../ingestion/requirements.txt -e agent_code
cd ../..
```

**Windows**
```powershell
cd $HOME\PycharmProjects\vs-langchain-agents\12-ecom-agent-project\agent\nlq
pip install -r ..\..\ingestion\requirements.txt -e agent_code
cd ..\..
```

## Deploy — prebuilt images (no Docker)

Use the tag the instructor published (`ecom-publish-images`). Start at the project root.

**Mac**
```bash
cd ~/PycharmProjects/vs-langchain-agents/12-ecom-agent-project
cd agent/nlq && python deploy.py --image prudhviakella898/ecom-nlq-agent:1.0 && cd ../..
cd agent/chart_gen && python deploy.py --image prudhviakella898/ecom-chart-gen-agent:1.0 && cd ../..
cd agent/supervisor && python deploy.py --image prudhviakella898/ecom-supervisor-agent:1.0 && cd ../..
```

**Windows**
```powershell
cd $HOME\PycharmProjects\vs-langchain-agents\12-ecom-agent-project
cd agent\nlq; python deploy.py --image prudhviakella898/ecom-nlq-agent:1.0; cd ..\..
cd agent\chart_gen; python deploy.py --image prudhviakella898/ecom-chart-gen-agent:1.0; cd ..\..
cd agent\supervisor; python deploy.py --image prudhviakella898/ecom-supervisor-agent:1.0; cd ..\..
```

With Docker Desktop running, drop `--image ...` to build locally instead.

## Smoke test — the whole chain

**Mac**
```bash
cd agent/supervisor && python ask.py "Which carrier delivers on time most often?" && cd ../..
```
**Windows**
```powershell
cd agent\supervisor; python ask.py "Which carrier delivers on time most often?"; cd ..\..
```

You see the plan, the SQL, row counts, the chart, the answer streaming, then a summary with
the table size, agents used, tokens and the trace id.

## Rules

- **Order is fixed:** NLQ creates the read-only database user and the shared key secrets;
  the supervisor reads NLQ's and chart_gen's `deployment.json` for their ARNs.
- **Run each `deploy.py` from its own folder.** A deploy.py copied into another folder deploys
  the wrong agent.
- **Re-runs are safe.** IAM propagation ("Role validation failed", "Access denied while
  validating ECR URI") is retried automatically; if it still fails, run the same command again.
