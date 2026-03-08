# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NeverRTFM** — Upload any PDF report, get a 30–60 second TikTok-style video summary, and ask live voice questions mid-playback. Built for the Gemini AI Hackathon.

## Commands

### Backend

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv pip install -e .

# Run locally (from repo root — main.py and pipeline.py live here)
uvicorn main:app --reload --port 8080
```

Swagger docs at `http://localhost:8080/docs`.

### Docker

```bash
docker build -t nevertrtfm .
docker run -p 8080:8080 --env-file .env nevertrtfm
```

### GCP Deployment

```bash
# Backend → Cloud Run
gcloud run deploy nevertrtfm-api --source . --region us-central1 --allow-unauthenticated
```

## Architecture

The backend is a FastAPI app (`main.py`) with three routers and a Google ADK `SequentialAgent` pipeline (`pipeline.py`). The pipeline runs as a FastAPI background task, updating an in-memory job store as each agent completes.

### Agent Pipeline (sequential, in order)

| Agent | Input → Output | Model |
|---|---|---|
| `ParserAgent` | PDF path → `session["manifest"]` | Gemini 2.0 Flash Vision |
| `NarrativeScriptAgent` | `manifest` → `session["narration_script"]` | Gemini 2.0 Flash |
| `TTSAgent` | `narration_script` → `session["tts_result"]` (audio + word timestamps) | Google Cloud TTS (Chirp HD) |
| `VideoScriptAgent` | `narration_script` + `tts_result` → `session["video_script"]` (Veo prompts) | Gemini 2.0 Flash |
| `VeoAgent` | `video_script` → `session["veo_clips"]` | Veo 2 via Vertex AI |
| `StitcherAgent` | clips + audio + timestamps → `session["final_video_uri"]` | ffmpeg on Cloud Run |

A separate **LiveAgent** runs as a persistent WebSocket (Gemini Live API) for real-time voice Q&A. It holds the `manifest` as system context and always ends answers with `"resuming now"` to trigger frontend video resume.

### Key Session State Keys

`file_path` → `manifest` → `narration_script` → `tts_result` + `video_script` → `veo_clips` → `final_video_uri`

### API Contract

```
POST /api/generate          multipart/form-data { file: PDF }
                            → { job_id, status: "processing" }

GET  /api/status/{job_id}   → { status, step, video_url }

WS   /api/live/{job_id}     send: PCM 16-bit audio bytes
                            recv: { type: "transcript", text }
                            "resuming now" in text → frontend resumes video
```

### File Layout (planned)

```
main.py              FastAPI app + CORS + router registration
pipeline.py          ADK SequentialAgent root + run_pipeline() — called by routers/generate.py
agents/
  parser.py          ParserAgent
  narrative_script.py NarrativeScriptAgent
  tts.py             TTSAgent
  video_script.py    VideoScriptAgent
  veo.py             VeoAgent
  stitcher.py        StitcherAgent
routers/
  generate.py        POST /api/generate
  status.py          GET  /api/status/{job_id}
  live.py            WS   /api/live/{job_id} + LiveAgent
tools/
  storage.py         Local filesystem (DEV_MODE=true) or GCS toggle
  job_store.py       In-memory job store (swap Firestore for prod)
```

### Storage

- `DEV_MODE=true` (default local): files written to `local_storage/{job_id}/`
- `DEV_MODE=false`: uses GCS buckets (`/uploads`, `/audio`, `/clips`, `/final`)

### Output Formats

- **Video**: 1080×1920 vertical MP4 (TikTok format)
- **Captions**: Generated as SRT from TTS word timestamps — pure function, no LLM
- **Veo clips**: one per scene, duration-matched to TTS `scene_timestamps`
