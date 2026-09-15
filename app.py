from datetime import date, timedelta
import os

import streamlit as st

from graph import plan_trip_stream
from models import TripRequest

st.set_page_config(page_title="Atlas | Your trip, thoughtfully planned", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background: radial-gradient(circle at 12% 0%, #e0f2fe 0, transparent 29%), radial-gradient(circle at 92% 10%, #fce7f3 0, transparent 24%), #fbfcff; }
    .hero { padding: 2.3rem 2.6rem; border-radius: 28px; color: #fff; background: linear-gradient(125deg, #0f172a, #155e75 55%, #0f766e); box-shadow: 0 18px 44px rgba(15, 23, 42, .22); margin-bottom: 1.5rem; }
    .hero h1 { font-size: 3.1rem; margin: 0; letter-spacing: -.08rem; }
    .hero p { font-size: 1.05rem; margin: .45rem 0 0; color: #dff7f4; }
    .eyebrow { color: #99f6e4; text-transform: uppercase; font-size: .72rem; font-weight: 700; letter-spacing: .12rem; }
    .section-card { padding: 1.3rem 1.45rem; border: 1px solid #e5e7eb; background: rgba(255,255,255,.82); border-radius: 18px; margin: .55rem 0 1.1rem; }
    .step { display: inline-block; margin-right: .55rem; padding: .25rem .62rem; color: #0f766e; background: #ccfbf1; border-radius: 999px; font-weight: 700; font-size: .78rem; }
    div[data-testid="stForm"] { border: 0; padding: 0; }
    .stButton > button, .stFormSubmitButton > button { border-radius: 12px; font-weight: 700; min-height: 46px; }
</style>
""", unsafe_allow_html=True)

CITIES = ["Amsterdam", "Bangkok", "Barcelona", "Berlin", "Bali", "Budapest", "Dubai", "Hong Kong", "Istanbul", "Jaipur", "Kyoto", "Lisbon", "London", "New Delhi", "New York", "Paris", "Prague", "Rome", "Seoul", "Singapore", "Sydney", "Tokyo", "Toronto", "Vienna", "Zurich"]
INTERESTS = ["Food", "History", "Museums", "Nature", "Nightlife", "Shopping", "Adventure", "Wellness", "Family activities", "Photography"]
STAGES = {
    "supervisor": (10, "Reading your travel brief and protecting every constraint"),
    "flights": (0, "Scanning current flight research"),
    "stay": (0, "Exploring the best areas to stay"),
    "activities": (0, "Pinning experiences, food, and hidden gems"),
    "weather": (0, "Checking weather and smart backup options"),
    "itinerary": (72, "Designing your day-by-day journey"),
    "route_budget": (84, "Checking pace, route flow, and budget"),
    "validator": (96, "Putting the plan through its final quality check"),
    "replan": (68, "Validator requested a thoughtful tune-up"),
}
RESEARCH_NODES = {"flights", "stay", "activities", "weather"}


def run_planner(request: TripRequest, feedback: str = "") -> dict:
    """Show LangGraph updates as a lively, transparent planning sequence."""
    final_state: dict = {"research": {}, "tool_data": {}}
    completed_research: set[str] = set()
    progress = st.progress(0, text="Packing the essentials for your planning journey…")
    with st.status("Atlas is planning your trip", expanded=True) as status:
        for update in plan_trip_stream(request, feedback):
            for node, payload in update.items():
                if node.startswith("__"):
                    continue
                for key, value in payload.items():
                    if key in {"research", "tool_data"}:
                        final_state[key].update(value)
                    else:
                        final_state[key] = value
                percent, label = STAGES.get(node, (50, "Planning your trip"))
                if node in RESEARCH_NODES:
                    completed_research.add(node)
                    percent = 10 + len(completed_research) * 12
                    label = f"{label}  ·  Research team: {len(completed_research)}/4 complete"
                progress.progress(percent, text=label)
                status.write(f"**{label}**")
        status.update(label="Your personalised itinerary is ready", state="complete", expanded=False)
    progress.progress(100, text="Ready to explore")
    return final_state


with st.sidebar:
    st.markdown("### ✦ How Atlas thinks")
    st.caption("Four independent specialists research in parallel, then Atlas designs, checks, and validates your itinerary.")
    st.markdown("""
    1. **Tell us the essentials**
    2. **Watch the planning journey**
    3. **Review and reshape your trip**
    """)
    st.divider()
    st.caption("Live research: Tavily, OpenStreetMap, OSRM, OpenWeather, and ExchangeRate-API. Availability is always labelled.")

st.markdown("""
<div class="hero">
  <div class="eyebrow">Multi-agent travel intelligence</div>
  <h1>Atlas plans the trip.<br>You make it yours.</h1>
  <p>From a few thoughtful choices to a realistic, reviewable itinerary — with a team of specialist agents behind it.</p>
</div>
""", unsafe_allow_html=True)

if not os.getenv("OPENAI_API_KEY"):
    st.warning("Add `OPENAI_API_KEY` to your local `.env` file before generating a plan. Keys are never displayed in this interface.")

st.markdown('<div class="section-card"><span class="step">STEP 1</span><b>Build your travel brief</b><br><small>Fields marked * are required so every specialist receives the same complete context.</small></div>', unsafe_allow_html=True)

with st.form("trip_form", clear_on_submit=False):
    trip_tab, taste_tab, details_tab = st.tabs(["✈️ Journey", "♡ Travel style", "✦ Final touches"])
    with trip_tab:
        left, right = st.columns(2)
        with left:
            departure_city = st.selectbox("Departing from *", CITIES, index=CITIES.index("New Delhi"))
            departure_date = st.date_input("Departure date *", min_value=date.today(), value=date.today() + timedelta(days=30))
            travelers = st.number_input("Travellers *", min_value=1, max_value=12, value=2)
        with right:
            destination_city = st.selectbox("Destination *", CITIES, index=CITIES.index("Tokyo"))
            return_date = st.date_input("Return date *", min_value=date.today() + timedelta(days=1), value=date.today() + timedelta(days=35))
            budget = st.number_input("Total trip budget *", min_value=1, value=150000, step=5000)
            currency = st.selectbox("Budget currency *", ["INR", "USD", "EUR", "GBP", "JPY", "AED", "SGD"])
    with taste_tab:
        one, two, three = st.columns(3)
        with one:
            travel_style = st.selectbox("Travel style *", ["Value", "Balanced", "Comfort", "Luxury"], index=1)
        with two:
            accommodation_level = st.selectbox("Accommodation *", ["Hostel", "Budget hotel", "Mid-range hotel", "Boutique hotel", "Luxury hotel"], index=2)
        with three:
            pace = st.selectbox("Daily pace *", ["Relaxed", "Balanced", "Packed"], index=1)
        interests = st.multiselect("What would make this trip memorable? *", INTERESTS, default=["Food", "History"])
        dietary_requirements = st.selectbox("Dietary needs *", ["None", "Vegetarian", "Vegan", "Halal", "Kosher", "Gluten-free", "Other"])
    with details_tab:
        extra_details = st.text_area("Anything else? (optional)", placeholder="Accessibility needs, a special occasion, must-see places, flight preference, or a dream experience…", height=130)
        st.info("Atlas will flag unknown live details instead of presenting guesses as confirmed bookings.")
    submitted = st.form_submit_button("Create my trip story  →", type="primary", use_container_width=True)

if submitted:
    try:
        request = TripRequest(departure_city=departure_city, destination_city=destination_city, departure_date=departure_date, return_date=return_date, travelers=travelers, budget=budget, currency=currency, travel_style=travel_style, accommodation_level=accommodation_level, interests=interests, dietary_requirements=dietary_requirements, pace=pace, extra_details=extra_details)
        if departure_city == destination_city:
            raise ValueError("Choose different departure and destination cities.")
        st.session_state.result = run_planner(request)
        st.session_state.request = request
    except Exception as exc:
        st.error(f"Atlas could not finish this plan: {exc}")

if result := st.session_state.get("result"):
    st.markdown('<div class="section-card"><span class="step">STEP 2</span><b>Your trip, ready for review</b><br><small>Use the validator report and your own judgement before making any booking.</small></div>', unsafe_allow_html=True)
    report = result.get("validation", {})
    status_col, trip_col, retry_col = st.columns(3)
    status_col.metric("Quality check", "Approved" if report.get("approved") else "Needs review")
    trip_col.metric("Days away", (st.session_state.request.return_date - st.session_state.request.departure_date).days)
    retry_col.metric("Planning revisions", result.get("replan_count", 0))
    (st.success if report.get("approved") else st.warning)(report.get("summary", "The validator completed its review."))
    if report.get("issues"):
        st.caption("Validator notes: " + "  •  ".join(report["issues"]))
    st.markdown("### Your itinerary")
    st.markdown(result.get("itinerary", ""))
    st.caption("Research and mapped-place data: © OpenStreetMap contributors. Route estimates are indicative; confirm real transport times before travelling.")

    with st.expander("Show research trail and source data"):
        st.json(result.get("tool_data", {}))

    st.markdown('<div class="section-card"><span class="step">STEP 3</span><b>Shape it with human judgement</b><br><small>Ask for a change; Atlas will rerun the specialist workflow with your feedback.</small></div>', unsafe_allow_html=True)
    feedback = st.text_area("What should change?", key="review_feedback", placeholder="For example: make Day 3 calmer, include more vegetarian street food, or swap museums for outdoor experiences.")
    if st.button("Reimagine my itinerary  →", type="primary"):
        if not feedback.strip():
            st.info("Add a note first, then Atlas can reshape the itinerary.")
        else:
            try:
                st.session_state.result = run_planner(st.session_state.request, feedback)
                st.rerun()
            except Exception as exc:
                st.error(f"Atlas could not revise this plan: {exc}")
