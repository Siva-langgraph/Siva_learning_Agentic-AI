"""The supervisor's routing decision — what the model may decide before any data is fetched.

    question + history ──► route model ──► RouteDecision
                                             action          query · answer · clarify
                                             questions       for query: 1-3 standalone questions
                                             chart_request   for query: the chart the USER asked for
                                             rationale       shown to the user
                                             reply           for answer: plain prose only
                                             clarifying_question · options   for clarify

WHY chart_request EXISTS
    "Show that as a line chart" is a request for a CHART of data already in
    the conversation. Without a field for it the only way out was `answer`,
    and the model then drew the chart itself as Mermaid text in `reply`.
    chart_request makes it a `query`: the data is fetched again (the previous
    table is not kept between turns) and chart_gen is told which chart type
    the user named.

WHAT THIS DOES NOT DO
    It does not draw anything. Charts are made by chart_gen only; `reply` is
    never a chart, a table or code.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    action: Literal["query", "answer", "clarify"] = Field(description=(
        "query: the question needs the store's data — INCLUDING any request to chart, plot or visualise data, "
        "even data already shown earlier in the conversation. answer: no data needed (greeting, what you can do, "
        "out of scope). clarify: the question is too ambiguous to query (say what is missing)."))
    questions: list[str] = Field(default_factory=list, max_length=3, description=(
        "For query: 1-3 STANDALONE questions for the data agent — resolve 'it', 'that month', 'the second one' "
        "from the conversation. For a chart of earlier data, restate the earlier data question in full "
        "('On-time delivery rate by carrier'). One question unless the user asked several distinct things."))
    chart_request: str = Field(default="", description=(
        "For query: the chart the user explicitly asked for, in a few words ('line chart', 'pie chart', "
        "'a chart', 'bar chart sorted by revenue'). Empty when the user did not ask for a chart."))
    rationale: str = Field(description="One or two sentences: why this plan. Shown to the user as reasoning.")
    reply: str = Field(default="", description=(
        "For answer: the reply itself, in plain sentences — never a chart, diagram, table, Mermaid or code. "
        "Empty otherwise."))
    clarifying_question: str = Field(default="", description="For clarify: the question to ask the user.")
    options: list[str] = Field(default_factory=list, max_length=4, description="For clarify: 2-4 short choices.")
