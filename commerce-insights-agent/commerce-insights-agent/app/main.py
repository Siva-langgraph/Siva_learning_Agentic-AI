from __future__ import annotations
import json, logging, queue, threading
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from .agent import answer_question
from .config import settings
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("commerce-insights")
app = FastAPI(title="Commerce Insights Agent", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_credentials=False, allow_methods=["GET","POST"], allow_headers=["Content-Type","X-API-Key"])
class ChatRequest(BaseModel): question: str = Field(min_length=1, max_length=2000)
def authenticate(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if settings.api_key and x_api_key != settings.api_key: raise HTTPException(status_code=401, detail="Invalid API key")
    if settings.app_env == "production" and not settings.api_key: raise HTTPException(status_code=503, detail="APP_API_KEY must be configured in production")
@app.get("/health")
def health(): return {"status":"ok", "service":"commerce-insights-agent"}
@app.post("/api/chat", dependencies=[Depends(authenticate)])
def chat(body: ChatRequest):
    try: return answer_question(body.question)
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        log.exception("agent request failed")
        raise HTTPException(502, "The agent request failed; check service logs and provider configuration") from exc
@app.post("/api/chat/stream", dependencies=[Depends(authenticate)])
def chat_stream(body: ChatRequest):
    def events():
        updates: queue.Queue = queue.Queue()
        sentinel = object()
        def emit(item): updates.put(("progress", item))
        def worker():
            try: updates.put(("done", answer_question(body.question, emit=emit)))
            except Exception:
                log.exception("streaming agent request failed")
                updates.put(("error", {"error":"Agent request failed"}))
            finally: updates.put(("end", sentinel))
        threading.Thread(target=worker, daemon=True).start()
        yield "event: status\ndata: " + json.dumps({"status":"started"}) + "\n\n"
        while True:
            kind, payload = updates.get()
            if kind == "end": break
            yield f"event: {kind}\ndata: {json.dumps(payload, default=str)}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control":"no-cache", "X-Accel-Buffering":"no"})
