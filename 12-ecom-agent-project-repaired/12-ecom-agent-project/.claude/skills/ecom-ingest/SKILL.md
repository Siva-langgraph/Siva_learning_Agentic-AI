---
name: ecom-ingest
description: Prepare the e-commerce data and load it — clean the 14 CSVs, build the knowledge-base workbook, create RDS PostgreSQL and load it, and publish the knowledge base to Pinecone. Use when setting up the e-commerce project's data, reloading the database, or when the agents need the database or the ecom-kb index.
---

# Ingest the e-commerce data

```
ingestion/data/raw/*.csv ─► prepare ─► data/clean/*.csv ─► deploy ─► RDS PostgreSQL  schema ecom
     (14 files)              │         DATA_DICTIONARY.md              your IP only · password in Secrets Manager
                             └──────► kb_feed/kb_feed_ecom.xlsx ─► pinecone ─► Pinecone ecom-kb
                                       (SQL examples, each executed)          nlq-schema · nlq-examples · common
```

Everything runs on your machine from `ingestion/`. Full guide: `ingestion/README.md`.

## Once

**Mac**
```bash
cd ~/PycharmProjects/vs-langchain-agents/12-ecom-agent-project/ingestion
pip install -r requirements.txt
cp .env.example .env            # then put PINECONE_API_KEY and OPENAI_API_KEY in it
```

**Windows**
```powershell
cd $HOME\PycharmProjects\vs-langchain-agents\12-ecom-agent-project\ingestion
python -m pip install -r requirements.txt
Copy-Item .env.example .env     # then put PINECONE_API_KEY and OPENAI_API_KEY in it
```

## The four steps — same commands on Mac and Windows, inside `ingestion/`

| Step | Command | Ends with |
|---|---|---|
| 1 prepare (offline) | `python run.py prepare` | `48 of 48 rules pass` · `✓ done` |
| 2 RDS + load (~10 min first time) | `python run.py deploy` | `examples: 61 of 61 run on PostgreSQL` · `✓ done` |
| 3 check the KB, sends nothing | `python run.py pinecone --dry-run` | every record checked |
| 4 publish the KB | `python run.py pinecone` | index `ecom-kb` (1536-d, cosine, `text-embedding-3-small`) |

`postgres/deployment.json` then holds host, region and the secret's full ARN — **no
password**. The NLQ agent's deploy reads it.

## Later

| Task | Command |
|---|---|
| reload the data | `python run.py postgres` |
| offline tests | `python run.py test` |
| delete RDS and its network pieces | `python run.py deploy --destroy` |
| your IP changed (new Wi-Fi, VPN) | `python run.py deploy` again — it adds the new IP |

Rotate the database password (do this if it was ever pasted anywhere):

**Mac**
```bash
dep() { python -c "import json; print(json.load(open('postgres/deployment.json'))['$1'])"; }
aws secretsmanager rotate-secret --region "$(dep region)" --secret-id "$(dep secret_arn)"
```

**Windows**
```powershell
$d = Get-Content postgres\deployment.json -Raw | ConvertFrom-Json
aws secretsmanager rotate-secret --region $d.region --secret-id $d.secret_arn
```

## Rules

- Never print, paste or store the database password. It lives in Secrets Manager.
- `.env` is never committed.
- The agents connect as the read-only user `ecom_reader` (created by the NLQ deploy), never as
  the master user.
- RDS costs about USD 15–20/month while it runs.
