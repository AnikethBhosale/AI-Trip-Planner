# Atlas AI Trip Planner

Atlas is a Streamlit-based, multi-agent travel itinerary planner built with LangGraph. It collects complete, structured trip information instead of relying on an open-ended prompt, researches the trip through specialist agents and live-provider adapters, produces an itinerary, validates it, and lets the traveller request a human-guided revision.

## What is implemented

- Required trip form fields for departure, destination, dates, traveller count, budget, currency, travel style, accommodation level, pace, interests, and dietary needs.
- Optional free-text field for special occasions, accessibility needs, must-see places, and other context.
- LangGraph orchestration with dedicated supervisor, flight, accommodation, activity/restaurant, weather, itinerary, route/budget, and validation agents.
- Live-data adapters for Tavily web research, OpenStreetMap places, OSRM route samples, OpenWeather, and ExchangeRate-API.
- Transparent fallback behavior: if a key is absent or a provider fails, the plan labels the data as unverified instead of inventing live availability or prices.
- Automatic quality validation and a bounded replan loop (two retries by default).
- A human-in-the-loop review panel where the traveller can ask for a revised plan after inspecting the result.
- Configuration through a local `.env` file, with a safe `.env.example` template and `.gitignore` protection.

## Architecture

```text
Streamlit form
    |
    v
TripRequest (Pydantic validation)
    |
    v
LangGraph workflow
    |
    +--> Supervisor: extracts and protects constraints
    +--> Flight specialist -----------+
    +--> Accommodation specialist ----+--> run in parallel, then join
    +--> Activity/restaurant specialist+
    +--> Weather specialist ----------+
    +--> Itinerary designer: day-by-day trip plan
    +--> Route/budget optimizer: pacing, geographic order, and budget audit
    +--> Final validator: quality gate
               |
               +--> issues found -> replan (maximum configured attempts)
               |
               +--> approved / retry limit reached -> traveller review
                                                    |
                                                    +--> optional human feedback -> new revision
```

### Project structure

| File | Responsibility |
| --- | --- |
| `app.py` | Streamlit UI, required form controls, results view, and human feedback loop. |
| `models.py` | `TripRequest` schema and date/traveller/budget validation. |
| `graph.py` | Agent prompts, LangGraph state, routing, automatic validation, and replanning. |
| `travel_tools.py` | Isolated HTTP adapters for external travel and information providers. |
| `config.py` | Environment-variable loading and shared configuration. |
| `.env.example` | Complete configuration template without secrets. |
| `requirements.txt` | Python dependencies. |

## How a planning request works

1. The traveller completes the form. Mandatory structured controls reduce missing details that can make plans unreliable.
2. Pydantic rejects invalid requests, such as a return date earlier than the departure date.
3. The supervisor establishes the non-negotiable requirements: budget, pace, dietary needs, accommodation preference, and interests.
4. Flight, accommodation, activity, and weather specialists gather information concurrently. LangGraph merges their independent state updates and waits for all four before itinerary generation begins.
5. The itinerary agent builds a day-by-day schedule with morning, afternoon, evening, transit buffers, food ideas, cost categories, and verification notes.
6. The route/budget agent checks whether the schedule is geographically plausible and consistent with the requested budget.
7. The validator checks dates, preferences, dietary needs, pacing, transit buffers, budget treatment, and caveats around unavailable live data. If it finds material problems, its issues are passed back to the itinerary agent for revision.
8. The traveller sees the itinerary and the validation report. They may enter feedback such as “fewer museums” or “more vegetarian street food,” then generate a revised plan using the form values, specialist research, and the prior itinerary as context.

## Agent responsibilities

| Agent | Purpose | Provider evidence when configured |
| --- | --- | --- |
| Supervisor | Converts the request into constraints for every downstream agent. | None required |
| Flight specialist | Summarizes current flight research and explains what to verify. | Tavily web search |
| Accommodation specialist | Recommends neighbourhoods and summarizes current accommodation research. | Tavily web search |
| Activity/restaurant specialist | Finds mapped attractions and food venues aligned with interests/diet. | OpenStreetMap / Overpass |
| Weather specialist | Adds weather context and indoor fallback ideas. | OpenWeather |
| Itinerary designer | Synthesizes all findings into the traveller-facing itinerary. | All previous agent outputs |
| Route/budget optimizer | Checks daily travel order, pacing, and cost reasoning. | OSRM route sample + ExchangeRate-API |
| Final validator | Acts as a quality gate and emits machine-readable approval/issues. | Itinerary + route/budget audit |

## Run locally

### Prerequisites

- Python 3.11 or newer
- An LLM API key compatible with `langchain-openai`
- Optional travel-provider keys for live results

### Setup

1. Confirm Python is installed:

   ```powershell
   py --version
   ```

   If this reports that no Python runtime is installed, install Python 3.11+ from [python.org](https://www.python.org/downloads/windows/). During installation, enable the option to add Python to PATH.

2. From the project folder, create a virtual environment:

   ```powershell
   py -3 -m venv .venv
   ```

3. Activate it in PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks local scripts, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for the current terminal, then activate the environment again.

4. Upgrade packaging tools and install packages:

   ```powershell
   py -m pip install --upgrade pip
   py -3 -m pip install -r requirements.txt
   ```

5. Open `.env` and add your credentials. The minimum required values are `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL`. The file already exists with blank placeholders; alternatively, recreate it from the template:

   ```powershell
   Copy-Item .env.example .env
   ```

6. Start Streamlit:

   ```powershell
   py -3 -m streamlit run app.py
   ```

   Streamlit will show a local URL, normally `http://localhost:8501`. Open it in a browser, complete the required trip form, and select **Create and validate itinerary**.

`OPENAI_BASE_URL` supports OpenAI-compatible LLM providers. `OPENAI_EMBEDDING_MODEL` is included for planned semantic memory/recommendation retrieval but embeddings are not sent in this MVP.

### Everyday commands

```powershell
# Activate the environment in a new terminal
.\.venv\Scripts\Activate.ps1

# Run the app
py -3 -m streamlit run app.py

# Stop the app
# Press Ctrl+C in the terminal running Streamlit
```

### Troubleshooting

| Problem | What to check |
| --- | --- |
| `No installed Python found` | Install Python 3.11+ and reopen PowerShell. |
| `No module named streamlit` | Activate `.venv`, then rerun `py -3 -m pip install -r requirements.txt`. |
| `OPENAI_API_KEY is missing` | Add a non-empty key in `.env`, save it, then stop and restart Streamlit. |
| A travel provider is marked unavailable | Add that provider's key to `.env`, verify it is enabled in the provider dashboard, then restart the app. |
| OpenStreetMap/OSRM is unavailable | Public services can be busy. Retry later; the itinerary retains clear unavailable-data notes. |

## Configuration

| Environment variable | Required | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Yes | LLM authentication. |
| `OPENAI_BASE_URL` | Yes | OpenAI or compatible API base URL. |
| `OPENAI_MODEL` | Yes | Chat/reasoning model used by agents. |
| `OPENAI_EMBEDDING_MODEL` | Future use | Embedding model reserved for semantic retrieval. |
| `OPENWEATHER_API_KEY` | Optional | Forecast evidence. |
| `EXCHANGERATE_API_KEY` | Optional | Currency conversion evidence. |
| `TAVILY_API_KEY` | Optional | Current flight/stay research and timely travel information. |
| `OSM_USER_AGENT` | Recommended | Identifies this low-volume prototype to OpenStreetMap services. |
| `MAX_REPLAN_ATTEMPTS` | Optional | Automatic retry limit; defaults to `2`. |
| `MAX_PARALLEL_AGENTS` | Optional | Maximum simultaneous research agents; defaults to `4`. |
| `REQUEST_TIMEOUT_SECONDS` | Optional | Provider request timeout; defaults to `20`. |

## API setup checklist

| Provider | Used for | How to obtain it |
| --- | --- | --- |
| OpenAI (or compatible LLM) | Agent reasoning and itinerary writing | Create an API key in your provider dashboard; set `OPENAI_API_KEY`, base URL, and model. [OpenAI quickstart](https://platform.openai.com/docs/quickstart) |
| OpenStreetMap + Overpass | Places, attractions, restaurants, and geocoding | No key is needed for this low-volume prototype. Set a meaningful `OSM_USER_AGENT`, follow public-service policies, and self-host or use a managed provider before production. [Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/), [Overpass guide](https://wiki.openstreetmap.org/wiki/Overpass_API) |
| OSRM | Indicative driving-route samples | No key is used for this prototype. The public demo service is not a production SLA; self-host or adopt a managed routing service for scale. [OSRM API docs](https://project-osrm.org/docs/) |
| OpenWeather | Destination forecast | Register, create a key, wait for activation, then set `OPENWEATHER_API_KEY`. [OpenWeather API](https://openweathermap.org/api) |
| ExchangeRate-API | Currency conversion evidence for budget checks | Create an account and copy the key into `EXCHANGERATE_API_KEY`. [ExchangeRate-API](https://www.exchangerate-api.com/) |
| Tavily | Current flight/stay research, closures, events, and disruptions | Create an account and copy its key into `TAVILY_API_KEY`. Results are exposed in the application's research trail. [Tavily Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search) |

## Current MVP limitations and next steps

- Research agents run concurrently for lower latency. Their completion order is intentionally non-deterministic and shown live in the UI.
- Public OpenStreetMap, Overpass, and OSRM endpoints are suitable only for low-volume experimentation. Respect their policies; self-host or use managed services before public launch.
- The app recommends and researches; it does not make bookings or store traveller profiles.
- Results are generated for the current session only. Add PostgreSQL for saved plans, Redis for caching, and a vector store for preference memory.
- Add a commercial or self-hosted routing engine with transit support for production-grade journey times.
- Render Tavily source links directly beside itinerary recommendations rather than only in the research trail.
- Add authentication, server-side secret management, structured logging, rate limiting, tests, and monitoring before public deployment.

## Security and operational notes

- Never commit or share `.env`. It is excluded through `.gitignore`.
- Keep all provider keys server-side; do not expose them in browser code.
- Restrict provider keys by API, IP/service account, and usage quota wherever the provider supports it.
- Live provider data, prices, and availability can change between research and booking. The itinerary should always be confirmed before purchasing.
- API pricing, coverage, booking privileges, and production access vary by provider. Review current provider terms before launch.
