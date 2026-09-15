"""LangGraph workflow: research specialists -> itinerary -> validation -> bounded replan."""
from __future__ import annotations

import json
from typing import Annotated, Any, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from config import settings
from models import TripRequest
from travel_tools import exchange_rates, flight_research, hotel_research, places, route_estimate, weather


def merge_dicts(current: dict[str, Any] | None, update: dict[str, Any] | None) -> dict[str, Any]:
    """Merge independent parallel-agent updates without losing another agent's result."""
    return {**(current or {}), **(update or {})}


class PlannerState(TypedDict, total=False):
    request: dict[str, Any]
    research: Annotated[dict[str, Any], merge_dicts]
    tool_data: Annotated[dict[str, Any], merge_dicts]
    itinerary: str
    validation: dict[str, Any]
    replan_count: int
    human_feedback: str


def _llm() -> ChatOpenAI:
    cfg = settings()
    if not cfg["openai_api_key"]:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to .env before generating a plan.")
    return ChatOpenAI(api_key=cfg["openai_api_key"], base_url=cfg["openai_base_url"], model=cfg["openai_model"], temperature=0.2)


def _ask(role: str, request: dict[str, Any], evidence: Any, output: str) -> str:
    prompt = f"""You are the {role} in a multi-agent trip-planning system.
Trip request: {json.dumps(request, default=str)}
Evidence from live tools (may be unavailable): {json.dumps(evidence, default=str)[:14000]}
{output}
Never invent availability, opening hours, prices, or reservations. Clearly label estimates and missing live data."""
    return _llm().invoke(prompt).content


def supervisor(state: PlannerState) -> dict:
    return {"research": {"supervisor": _ask("supervisor", state["request"], {}, "Identify constraints every specialist must respect in a compact checklist.")}}


def flight_agent(state: PlannerState) -> dict:
    r = state["request"]
    evidence = flight_research(r["departure_city"], r["destination_city"], r["departure_date"], r["return_date"], r["travelers"])
    return {"research": {"flights": _ask("flight research specialist", r, evidence, "Summarize reputable current sources. Never quote a price or availability as confirmed; advise the traveller to verify it with the airline or booking provider.")}, "tool_data": {"flights": evidence}}


def stay_agent(state: PlannerState) -> dict:
    r = state["request"]
    evidence = hotel_research(r["destination_city"], r["departure_date"], r["return_date"], r["travelers"])
    return {"research": {"stay": _ask("accommodation research specialist", r, evidence, "Recommend neighbourhoods and summarize reputable research. Do not claim real-time hotel availability without a booking-provider confirmation.")}, "tool_data": {"stays": evidence}}


def activity_agent(state: PlannerState) -> dict:
    r = state["request"]
    evidence = places(r["destination_city"], r["interests"])
    return {"research": {"activities": _ask("activity and restaurant specialist", r, evidence, "Suggest a geographically sensible, preference-aware shortlist with indoor backups. State that opening hours must be verified.")}, "tool_data": {"places": evidence}}


def weather_agent(state: PlannerState) -> dict:
    r = state["request"]
    evidence = weather(r["destination_city"])
    return {"research": {"weather": _ask("weather specialist", r, evidence, "Identify weather caveats and indoor/outdoor contingency guidance.")}, "tool_data": {"weather": evidence}}


def itinerary_agent(state: PlannerState) -> dict:
    r = state["request"]
    evidence = {"specialist_research": state["research"], "previous_itinerary": state.get("itinerary", "")}
    revision_instruction = ""
    if state.get("human_feedback"):
        revision_instruction = " Revise the previous itinerary in response to this feedback: " + state["human_feedback"]
    return {"itinerary": _ask("itinerary designer", r, evidence, "Create a day-by-day itinerary. Include morning/afternoon/evening, sensible zones, transit buffers, estimated cost categories, food compatible with diet, and verification notes." + revision_instruction)}


def route_budget_agent(state: PlannerState) -> dict:
    r = state["request"]
    evidence = {"itinerary": state["itinerary"], "exchange_rates": exchange_rates(r["currency"]), "route_sample": route_estimate(state.get("tool_data", {}).get("places", {}))}
    return {"research": {"route_budget": _ask("route and budget optimizer", r, evidence, "Audit travel order, daily pacing, and total cost against the stated budget. Treat the routing sample as a rough driving estimate, not public-transit truth. Return specific corrections.")}, "tool_data": {"route_budget": evidence}}


def validator(state: PlannerState) -> dict:
    raw = _ask("strict final validator", state["request"], {"itinerary": state["itinerary"], "route_budget": state["research"].get("route_budget", "")}, 'Return ONLY valid JSON: {"approved": boolean, "issues": [string], "summary": string}. Approve only if dates, budget, pace, dietary needs, realistic transit buffers, data caveats, and preferences are adequately handled.')
    try:
        report = json.loads(raw.removeprefix("```json").removesuffix("```").strip())
        report["approved"] = bool(report.get("approved"))
    except (json.JSONDecodeError, AttributeError):
        report = {"approved": False, "issues": ["Validator response was not machine-readable; perform a cautious revision."], "summary": raw}
    return {"validation": report}


def next_step(state: PlannerState) -> str:
    if state["validation"].get("approved") or state.get("replan_count", 0) >= int(settings()["max_replans"]):
        return "end"
    return "replan"


def replan(state: PlannerState) -> dict:
    feedback = "; ".join(state["validation"].get("issues", []))
    return {"replan_count": state.get("replan_count", 0) + 1, "human_feedback": feedback}


def build_graph():
    workflow = StateGraph(PlannerState)
    for name, node in [("supervisor", supervisor), ("flights", flight_agent), ("stay", stay_agent), ("activities", activity_agent), ("weather", weather_agent), ("itinerary", itinerary_agent), ("route_budget", route_budget_agent), ("validator", validator), ("replan", replan)]:
        workflow.add_node(name, node)
    workflow.add_edge(START, "supervisor")
    workflow.add_edge("supervisor", "flights")
    workflow.add_edge("supervisor", "stay")
    workflow.add_edge("supervisor", "activities")
    workflow.add_edge("supervisor", "weather")
    # Fan in only once every independent research specialist has completed.
    workflow.add_edge(["flights", "stay", "activities", "weather"], "itinerary")
    workflow.add_edge("itinerary", "route_budget")
    workflow.add_edge("route_budget", "validator")
    workflow.add_conditional_edges("validator", next_step, {"end": END, "replan": "replan"})
    workflow.add_edge("replan", "itinerary")
    return workflow.compile()


def plan_trip(request: TripRequest, feedback: str = "") -> PlannerState:
    # Keep native date objects in graph state for provider adapters. _ask() serializes
    # them safely for the LLM with json.dumps(..., default=str).
    return build_graph().invoke({"request": request.model_dump(), "research": {}, "tool_data": {}, "replan_count": 0, "human_feedback": feedback}, {"max_concurrency": int(settings()["max_parallel_agents"])})


def plan_trip_stream(request: TripRequest, feedback: str = ""):
    """Yield completed graph-node updates so Streamlit can show a live planning journey."""
    initial_state = {"request": request.model_dump(), "research": {}, "tool_data": {}, "replan_count": 0, "human_feedback": feedback}
    for update in build_graph().stream(initial_state, {"max_concurrency": int(settings()["max_parallel_agents"])}, stream_mode="updates"):
        yield update
