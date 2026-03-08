# NeverRTFM

> Upload any report. Get a 30–60 second TikTok-style video. Ask questions live.

---

## Prerequisites

- Python 3.13+
- [uv](https://astral.sh/uv) — fast Python package manager
- [Docker](https://docs.docker.com/get-docker/) + Docker Compose (optional)
- A Google Cloud project with the following APIs enabled:
  - Vertex AI (Gemini 2.0 Flash, Veo 2)
  - Cloud Text-to-Speech
  - Cloud Storage
- A GCP service account key with access to the above

---

## Setup

### 1. Clone & configure env

```bash
git clone <repo-url>
cd we-winning-ia

cp backend/.env backend/.env.local   # make a personal copy if needed
```

Edit `backend/.env`:

```env
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json

DEV_MODE=true          # keeps files local, no GCS needed
GCS_BUCKET=nevertrtfm  # only used when DEV_MODE=false
FRONTEND_URL=http://localhost:3000
```

### 2. Install uv (if you don't have it)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Install dependencies

```bash
cd backend
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e .
```

### 4. Run the backend

```bash
uvicorn main:app --reload --port 8080
```

API: `http://localhost:8080`
Swagger: `http://localhost:8080/docs`

---

## Running with Docker

```bash
# From repo root
docker compose up --build
```

For hot reload during development:

```bash
docker compose watch
```

---

## Project Structure

```
backend/
├── main.py           — FastAPI app, CORS, router registration
├── pipeline.py       — ADK SequentialAgent root, run_pipeline()
├── agents/
│   ├── parser.py           — PDF → manifest (Gemini 2.0 Flash Vision)
│   ├── narrative_script.py — manifest → script (Gemini 2.0 Flash)
│   ├── tts.py              — script → audio + timestamps (Cloud TTS Chirp HD)
│   ├── video_script.py     — script + timestamps → Veo prompts (Gemini 2.0 Flash)
│   ├── veo.py              — prompts → video clips (Veo 2)
│   └── stitcher.py         — clips + audio → final MP4 (ffmpeg)
├── routers/
│   ├── generate.py   — POST /api/generate
│   ├── status.py     — GET  /api/status/{job_id}
│   └── live.py       — WS   /api/live/{job_id}
└── tools/
    ├── job_store.py  — in-memory job state (swap Firestore for prod)
    └── storage.py    — local filesystem (DEV_MODE=true) or GCS toggle
```

---

## API

```
POST /api/generate
  Body: multipart/form-data { file: <PDF> }
  Returns: { job_id, status: "processing" }

GET /api/status/{job_id}
  Returns: { status: "processing"|"done"|"error", step, video_url }

WS /api/live/{job_id}
  Send: PCM 16-bit audio bytes
  Recv: { type: "transcript", text }
        → "resuming now" in text means frontend should resume video
```

---

## Team Assignments

| Who | Files |
|-----|-------|
| Person 1 | `agents/parser.py`, `agents/narrative_script.py`, GCP infra |
| Person 2 | `agents/tts.py`, `agents/video_script.py` |
| Person 3 | `agents/veo.py`, `agents/stitcher.py`, `tools/storage.py` |
| Person 4 | `routers/live.py`, `tools/job_store.py`, frontend |

---

## GCP Deployment

```bash
# Backend → Cloud Run
cd backend
gcloud run deploy nevertrtfm-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated

# Frontend → Firebase
cd frontend
npm run build
firebase deploy
```
