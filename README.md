# CareWatch

CareWatch is an AI-powered caretaker abuse detection MVP for vulnerable dependents, combining pose-based motion heuristics, Gemini scene verification, rolling clip capture, push notification escalation, SQLite logging, and a React dashboard.

The dashboard supports both live monitoring and uploaded recording review, so demos can show the current room feed and retrospective analysis of saved footage.

## Repository Layout

- `api/`, `core/`, `frontend/`, `main.py`: backend and web dashboard
- `EyeQ_IOS/`: iPhone app
- `requirements.txt`, `.env.example`: root runtime setup

## Setup

1. Create the environment file:
   - `cp .env.example .env`
2. Fill in the required secrets in `.env`:
   - `OPENROUTER_API_KEY`
   - `OPENROUTER_MODEL` (optional, defaults to `google/gemma-3-12b-it:free`)
   - `GEMINI_API_KEY`
   - `IOS_BUNDLE_ID`
   - `APNS_KEY_ID`
   - `APNS_TEAM_ID`
   - `APNS_AUTH_KEY_PATH`
3. Install Python dependencies:
   - `uv python install 3.11`
   - `uv venv .venv --python 3.11`
   - `uv pip install --python .venv/bin/python -r requirements.txt`
4. Install frontend dependencies:
   - `cd frontend && npm install`

## How To Run

Open two terminals from the project root.

Backend:
- `./.venv/bin/python main.py`

Frontend:
- `cd frontend`
- `npm run dev`

App URLs:
- API: `http://localhost:8000`
- Dashboard: `http://localhost:3000`

## How It Works

- `core/detector.py` runs YOLOv8-pose and flags proximity + fast-motion interactions or long caretaker absence.
- `core/classifier.py` sends flagged frames to the configured hosted or local vision model stack and enforces review cooldowns.
- `core/clip_saver.py` maintains a rolling 30-second frame buffer and saves evidence clips into `clips/`.
- `core/alert.py` sends app push alerts with 5-minute severity deduplication and logs every alert attempt.
- `core/pipeline.py` orchestrates capture, detection, classification, clip saving, alerting, and SQLite event logging.
- `api/` exposes the stream controls, status endpoint, alert feed, and clip playback API.
- `frontend/` provides the live operations dashboard.
- `EyeQ_IOS/` provides the guardian-facing mobile client.

## How To Demo For Judges

1. Start the backend and frontend, then open the dashboard to show the monitoring status panel and empty alert feed.
2. Click `Start Monitoring` and show the status change to active with uptime increasing.
3. Feed the camera a staged high-risk interaction or caretaker-absence scenario so the heuristic detector triggers Gemini review.
4. Show the resulting app notification, alert feed entry, and saved clip appearing in the dashboard with severity, reason, and suggested action.
5. Open `Review Clip` and explain that the family sees 30s clip with AI explanation, not 8 hours of footage
