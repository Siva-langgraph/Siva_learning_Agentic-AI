"""Chart requests — "give me that as a line chart" must reach chart_gen, never become Mermaid text.

    route (scripted) ─► query + chart_request ─► NLQ (stub) ─► chart_gen (stub, payload recorded) ─► compose

    The bug this guards: the router answered a chart follow-up itself (`answer`)
    and drew the chart as a ```mermaid block, so the web app showed raw text.

    No PostgreSQL and no A2A servers: specialists.call is replaced, so these run
    anywhere (the end-to-end chain is in test_supervisor_chain.py).
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

from langchain_core.messages import AIMessageChunk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_code"))

from supervisor import core, specialists  # noqa: E402
from supervisor.prompt import COMPOSE_PROMPT, ROUTE_PROMPT  # noqa: E402
from supervisor.schemas import RouteDecision  # noqa: E402

COLS = ["carrier", "on_time_pct"]
ROWS = [["UPS", 41.9], ["USPS", 41.6], ["FedEx", 41.2], ["DHL", 40.9], ["OnTrac", 40.5]]
LINE = {"chart_type": "line", "insight": "line joins carriers, not a trend — UPS leads",
        "figures": [{"data": [{"type": "scatter", "mode": "lines+markers"}], "layout": {}}], "usage": {}}


class Route:
    def __init__(self, decision): self.decision = decision
    def with_structured_output(self, schema, method, include_raw): return self
    async def ainvoke(self, messages):
        return {"parsed": self.decision, "raw": NS(usage_metadata={})}


class Compose:
    async def astream(self, messages):
        self.seen = messages
        yield AIMessageChunk(content="UPS is on time most often, at **41.9%**.")


def run(monkeypatch, decision, rows=ROWS, chart=LINE, question="give me in the form of a line chart"):
    calls = []

    async def fake_call(agent, payload, on_event, conversation_id):
        calls.append((agent, payload))
        if agent == "nlq":
            return {"columns": COLS, "rows": rows, "row_count": len(rows), "result_shape": "table",
                    "sql": "SELECT carrier FROM ecom.shipments", "usage": {}}
        return dict(chart)

    monkeypatch.setattr(specialists, "call", fake_call)
    compose = Compose()
    history = [{"role": "user", "text": "What is the on-time delivery rate by carrier?"},
               {"role": "assistant", "text": "UPS 41.9%, USPS 41.6%, FedEx 41.2%, DHL 40.9%, OnTrac 40.5%."}]

    async def go():
        return [ev async for ev in core.orchestrate(question, history, "conv-1",
                                                    route_model=Route(decision), compose_model=compose)]
    return asyncio.run(go()), calls, compose


FOLLOW_UP = RouteDecision(action="query", questions=["On-time delivery rate by carrier"],
                          chart_request="line chart", rationale="Re-run on-time rate by carrier and draw it as a line.")


def test_a_chart_follow_up_reaches_chart_gen_with_the_requested_type(monkeypatch):
    events, calls, _ = run(monkeypatch, FOLLOW_UP)
    chart_payload = next(p for a, p in calls if a == "chart_gen")
    assert chart_payload["chart_request"] == "line chart"
    # chart_gen gets the DATA question, not just "give me in the form of a line chart"
    assert chart_payload["question"].startswith("On-time delivery rate by carrier")
    assert chart_payload["rows"] == ROWS
    f = events[-1]
    assert f["artifacts"]["charts"][0]["chart_type"] == "line" and "chart_gen" in f["agents_used"]
    assert f["plan_record"]["chart_request"] == "line chart"
    assert "Chart requested: line chart" in f["reasoning"]


def test_a_requested_chart_is_drawn_even_below_chart_min_rows(monkeypatch):
    two = ROWS[:2]                                       # below chart_min_rows (3): normally no chart call
    _, calls, _ = run(monkeypatch, FOLLOW_UP, rows=two)
    assert any(a == "chart_gen" for a, _ in calls)
    plain = RouteDecision(action="query", questions=["On-time delivery rate by carrier"], rationale="r")
    _, calls, _ = run(monkeypatch, plain, rows=two)
    assert not any(a == "chart_gen" for a, _ in calls)  # unchanged without a request


def test_the_composer_is_told_what_was_charted(monkeypatch):
    _, _, compose = run(monkeypatch, FOLLOW_UP)
    assert "CHART: the user asked for: line chart. drawn as line" in compose.seen[-1].content
    none = {"chart_type": "none", "insight": "one point only", "figures": [], "usage": {}}
    _, _, compose = run(monkeypatch, FOLLOW_UP, chart=none)
    assert "CHART: the user asked for: line chart. none drawn — one point only" in compose.seen[-1].content


def test_without_a_request_chart_gen_gets_an_empty_chart_request(monkeypatch):
    plain = RouteDecision(action="query", questions=["On-time delivery rate by carrier"], rationale="r")
    _, calls, _ = run(monkeypatch, plain, question="What is the on-time delivery rate by carrier?")
    payload = next(p for a, p in calls if a == "chart_gen")
    assert payload["chart_request"] == "" and payload["question"] == "What is the on-time delivery rate by carrier?"


def test_a_drawn_chart_in_a_direct_reply_is_never_streamed(monkeypatch):
    """The guard behind the prompt: a ```mermaid block in an `answer` reply is removed."""
    drawn = RouteDecision(action="answer", rationale="r", reply=(
        "Here it is:\n```mermaid\nxychart-beta\n  line [41.6, 40.5]\n```"))
    events, calls, _ = run(monkeypatch, drawn)
    text = events[-1]["text"]
    assert "```" not in text and "mermaid" not in text and text == "Here it is:"
    assert "".join(e["text"] for e in events if e["type"] == "token") == text
    assert "Removed a drawn chart" in events[-1]["reasoning"] and calls == []

    only_chart = RouteDecision(action="answer", rationale="r", reply="```mermaid\nxychart-beta\n```")
    events, _, _ = run(monkeypatch, only_chart)
    assert "real chart" in events[-1]["text"] and "```" not in events[-1]["text"]


def test_a_plain_reply_is_untouched(monkeypatch):
    hi = RouteDecision(action="answer", rationale="greeting", reply="Hi! Ask me about orders or revenue.")
    events, _, _ = run(monkeypatch, hi, question="hi")
    assert events[-1]["text"] == "Hi! Ask me about orders or revenue." and "Removed" not in events[-1]["reasoning"]


def test_the_prompts_route_charts_to_query_and_forbid_drawing():
    assert "CHART REQUESTS ARE ALWAYS `query`" in ROUTE_PROMPT and "chart_request" in ROUTE_PROMPT
    assert "never a chart, diagram, table, Mermaid" in ROUTE_PROMPT
    assert "Never draw a chart yourself" in COMPOSE_PROMPT
    assert "chart_request" in RouteDecision.model_fields
