# DocuReel
> Upload any report. Get a 30-60 second TikTok-style video. Ask questions live.

---

## Setup (Do This First — Everyone)

```bash
git clone <repo>
cd docureel

# Copy env files
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local

# Fill in your API keys in backend/.env
```
docureel/
├── README.md                ← setup + API contract
├── backend/
│   ├── main.py              ← FastAPI app
│   ├── pipeline.py          ← ADK SequentialAgent root
│   ├── pyproject.toml       ← uv dependencies
│   ├── Dockerfile           ← ffmpeg + uv + Cloud Run ready
│   ├── .env.example
│   ├── agents/
│   │   ├── parser.py        ← Person 1
│   │   ├── narrative_script.py ← Person 1
│   │   ├── tts.py           ← Person 2
│   │   ├── video_script.py  ← Person 2
│   │   ├── veo.py           ← Person 3
│   │   └── stitcher.py      ← Person 3
│   ├── routers/
│   │   ├── generate.py
│   │   ├── status.py
│   │   └── live.py          ← Person 4
│   └── tools/
│       ├── storage.py       ← local dev / GCS toggle
│       └── job_store.py     ← in-memory, swap Firestore for prod
└── frontend/
    ├── package.json         ← Next.js
    ├── firebase.json        ← Firebase deploy config
    └── .env.local.example
    
---

## Backend (Person 1, 2, 3)

```bash
cd backend

# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -e .

# Run locally
uvicorn main:app --reload --port 8080
```

API will be live at `http://localhost:8080`  
Swagger docs at `http://localhost:8080/docs`

---

## Frontend (Person 4)

```bash
cd frontend
npm install
npm run dev
```

Frontend at `http://localhost:3000`

---

## Architecture

```
SequentialAgent: DocuReel
├── [1] ParserAgent          PDF → manifest           (Person 1)
├── [2] NarrativeScriptAgent manifest → script        (Person 1)
├── [3] TTSAgent             script → audio+timestamps (Person 2)
├── [4] VideoScriptAgent     script+tts → veo prompts  (Person 2)
├── [5] VeoAgent             prompts → video clips     (Person 3)
└── [6] StitcherAgent        everything → final video  (Person 3)

LiveAgent (always on WebSocket)                        (Person 4)
```

## Session State Keys

| Key | Owner | Description |
|-----|-------|-------------|
| `file_path` | pipeline.py | Input PDF path |
| `manifest` | ParserAgent | Structured report JSON |
| `narration_script` | NarrativeScriptAgent | TikTok script scenes |
| `tts_result` | TTSAgent | Audio path + word timestamps |
| `video_script` | VideoScriptAgent | Veo prompts per scene |
| `veo_clips` | VeoAgent | Video clip paths |
| `final_video_uri` | StitcherAgent | Signed URL to final MP4 |

## API Contract (Person 4 ↔ Backend)

```
POST /api/generate
  Body: multipart/form-data { file: PDF }
  Returns: { job_id: string, status: "processing" }

GET /api/status/{job_id}
  Returns: { status: "processing|done|error", step: string, video_url: string|null }

WS /api/live/{job_id}
  Send: audio bytes (PCM 16-bit)
  Receive: { type: "transcript", text: string }
           text contains "resuming now" → trigger video resume on frontend
```

## GCP Deployment (Person 1 handles when ready)

```bash
# Backend → Cloud Run
cd backend
gcloud run deploy docureel-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated

# Frontend → Firebase
cd frontend
npm run build
firebase deploy
```

## Local Storage

In `DEV_MODE=true`, files are stored in `backend/local_storage/{job_id}/`  
In production, swap to GCS by setting `DEV_MODE=false` in `.env`
