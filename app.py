from datetime import date, timedelta
import os

import streamlit as st

from graph import plan_trip
from models import TripRequest

st.set_page_config(page_title="Atlas AI Trip Planner", page_icon="✈️", layout="wide")
st.title("Atlas AI Trip Planner")
st.caption("Structured trip inputs, specialist agents, automatic validation, and your final approval.")

CITIES = ["Amsterdam", "Bangkok", "Barcelona", "Berlin", "Dubai", "Istanbul", "London", "New Delhi", "New York", "Paris", "Rome", "Singapore", "Sydney", "Tokyo"]
INTERESTS = ["Food", "History", "Museums", "Nature", "Nightlife", "Shopping", "Adventure", "Wellness", "Family activities", "Photography"]

if not os.getenv("OPENAI_API_KEY"):
    st.warning("Add your credentials to `.env` (copy from `.env.example`) before generating a live plan.")

with st.form("trip_form"):
    left, right = st.columns(2)
    with left:
        departure_city = st.selectbox("Departing from *", CITIES, index=7)
        destination_city = st.selectbox("Destination *", CITIES, index=13)
        departure_date = st.date_input("Departure date *", min_value=date.today(), value=date.today() + timedelta(days=30))
        return_date = st.date_input("Return date *", min_value=date.today() + timedelta(days=1), value=date.today() + timedelta(days=35))
        travelers = st.number_input("Travellers *", min_value=1, max_value=12, value=2)
    with right:
        budget = st.number_input("Total trip budget *", min_value=1, value=150000, step=5000)
        currency = st.selectbox("Budget currency *", ["INR", "USD", "EUR", "GBP", "JPY", "AED", "SGD"])
        travel_style = st.selectbox("Travel style *", ["Value", "Balanced", "Comfort", "Luxury"])
        accommodation_level = st.selectbox("Accommodation *", ["Hostel", "Budget hotel", "Mid-range hotel", "Boutique hotel", "Luxury hotel"])
        pace = st.selectbox("Daily pace *", ["Relaxed", "Balanced", "Packed"])
    interests = st.multiselect("Interests *", INTERESTS, default=["Food", "History"])
    dietary_requirements = st.selectbox("Dietary needs *", ["None", "Vegetarian", "Vegan", "Halal", "Kosher", "Gluten-free", "Other"])
    extra_details = st.text_area("Anything else? (optional)", placeholder="Accessibility needs, a special occasion, must-see places, flight preference…")
    submitted = st.form_submit_button("Create and validate itinerary", type="primary")

if submitted:
    try:
        request = TripRequest(departure_city=departure_city, destination_city=destination_city, departure_date=departure_date, return_date=return_date, travelers=travelers, budget=budget, currency=currency, travel_style=travel_style, accommodation_level=accommodation_level, interests=interests, dietary_requirements=dietary_requirements, pace=pace, extra_details=extra_details)
        if departure_city == destination_city:
            raise ValueError("Departure and destination must be different.")
        with st.spinner("The specialist agents are researching, planning, and validating…"):
            st.session_state.result = plan_trip(request)
            st.session_state.request = request
    except Exception as exc:
        st.error(str(exc))

if result := st.session_state.get("result"):
    report = result["validation"]
    (st.success if report.get("approved") else st.warning)("Automated validator: " + ("approved" if report.get("approved") else "review needed"))
    st.write(report.get("summary", ""))
    if report.get("issues"):
        st.caption("Checks: " + " • ".join(report["issues"]))
    st.subheader("Your itinerary")
    st.markdown(result["itinerary"])
    with st.expander("See specialist research"):
        st.json(result.get("research", {}))
    st.subheader("Human review")
    feedback = st.text_area("Request changes or approval notes", key="review_feedback", placeholder="e.g. Fewer museums, more street food, or reduce daily walking.")
    if st.button("Revise with my feedback"):
        if not feedback.strip():
            st.info("Enter feedback first, then request a revision.")
        else:
            with st.spinner("Replanning with your review…"):
                st.session_state.result = plan_trip(st.session_state.request, feedback)
            st.rerun()

