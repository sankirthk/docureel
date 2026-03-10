# DocuReel — Project & Agent Logic Flow
> Upload any report. Get a 30-60 second TikTok-style video. Ask questions live.

---

## What It Does

A user uploads a corporate or project report (PDF). The system produces a punchy,
cinematic short-form video summarizing the key insights — think a Bloomberg explainer
or a TikTok, not a slideshow. While watching, the user can interrupt with a voice
question at any time. The video pauses, a live AI agent answers from the full report,
and the video resumes.

---

## The User Flow

```
1. User uploads PDF report
2. Clicks "Generate"
3. ~60 seconds of processing
4. Short-form video plays (30-60s, TikTok style)
5. User speaks: "Wait, why did revenue drop?"
6. Video PAUSES
7. Live Agent answers using full report context
8. Agent says "resuming now" → video CONTINUES
```

---

## Agent Pipeline

```
SequentialAgent: "DocuReel"
│
├── [1] ParserAgent
│         Gemini 2.0 Flash Vision
│         IN:  PDF (GCS URI)
│         OUT: session["manifest"]
│
├── [2] NarrativeScriptAgent
│         Gemini 2.0 Flash
│         IN:  session["manifest"]
│         OUT: session["narration_script"]
│
├── [3] TTSAgent
│         Google Cloud TTS (Chirp HD)
│         IN:  session["narration_script"]
│         OUT: session["tts_result"]
│              (audio file + word-level timestamps + scene timestamps)
│
├── [4] VideoScriptAgent
│         Gemini 2.0 Flash
│         IN:  session["narration_script"] + session["tts_result"]
│         OUT: session["video_script"]
│              (Veo prompt per scene, time-aligned to audio)
│
├── [5] VeoAgent
│         Veo 2 via Vertex AI
│         IN:  session["video_script"]
│         OUT: session["veo_clips"]  (GCS URIs, one per scene)
│
└── [6] StitcherAgent
          ffmpeg on Cloud Run
          IN:  session["veo_clips"]
               session["tts_result"].audio_gcs_uri
               session["tts_result"].word_timestamps  ← captions generated here as pure function
          OUT: session["final_video_uri"]  (GCS signed URL)

─────────────────────────────────────────────
PARALLEL & ALWAYS ON:

[7] LiveAgent
      Gemini Live API (WebSocket)
      IN:  session["manifest"] as system context
           user voice stream
      OUT: voice response → triggers frontend PAUSE/RESUME
```

---

## What Each Agent Outputs

### [1] ParserAgent → `session["manifest"]`
```json
{
  "title": "Q3 2025 Revenue Report",
  "type": "corporate",
  "total_pages": 24,
  "key_sections": [
    {
      "id": 1,
      "heading": "Revenue Overview",
      "summary": "Total revenue fell 8% YoY driven by supply chain disruption.",
      "key_stats": ["Revenue: $4.2B", "YoY: -8%", "EBITDA margin: 12%"],
      "page": 3
    },
    {
      "id": 2,
      "heading": "Regional Performance",
      "summary": "APAC grew 14% while North America declined 11%.",
      "key_stats": ["APAC: +14%", "NA: -11%", "EMEA: flat"],
      "page": 7
    }
  ],
  "overall_summary": "Mixed quarter. Strong APAC offset by NA headwinds.",
  "sentiment": "cautious"
}
```

---

### [2] NarrativeScriptAgent → `session["narration_script"]`
```json
{
  "hook": "Your Q3 report in 45 seconds. Here's what actually matters.",
  "scenes": [
    {
      "scene_id": 1,
      "section_id": 1,
      "narration": "Revenue dropped 8% year over year. Supply chain issues hit hard.",
      "caption": "📉 Revenue: $4.2B | -8% YoY",
      "tone": "urgent"
    },
    {
      "scene_id": 2,
      "section_id": 2,
      "narration": "But APAC surged 14%. That's your bright spot going into Q4.",
      "caption": "🌏 APAC: +14% — the silver lining",
      "tone": "optimistic"
    }
  ],
  "outro": "Full report in your inbox. Now you know what to ask in the meeting."
}
```

---

### [3] TTSAgent → `session["tts_result"]`
```json
{
  "audio_gcs_uri": "gs://docureel/audio/session_abc.wav",
  "duration_seconds": 43.2,
  "word_timestamps": [
    {"word": "Revenue",  "start": 1.1, "end": 1.5},
    {"word": "dropped",  "start": 1.5, "end": 1.9},
    {"word": "8%",       "start": 1.9, "end": 2.2}
  ],
  "scene_timestamps": [
    {"scene_id": 1, "start": 0.0,  "end": 8.4},
    {"scene_id": 2, "start": 8.5,  "end": 16.2}
  ]
}
```

---

### [4] VideoScriptAgent → `session["video_script"]`
```json
{
  "veo_prompts": [
    {
      "scene_id": 1,
      "start": 0.0,
      "end": 8.4,
      "prompt": "Cinematic close-up of falling stock ticker, dark dramatic lighting, 4K",
      "style": "corporate dramatic"
    },
    {
      "scene_id": 2,
      "start": 8.5,
      "end": 16.2,
      "prompt": "Aerial shot of glowing Asian city skyline at night, optimistic energy, 4K",
      "style": "corporate optimistic"
    }
  ]
}
```

---

### [5] VeoAgent → `session["veo_clips"]`
```json
{
  "clips": [
    {"scene_id": 1, "gcs_uri": "gs://docureel/clips/scene1.mp4", "duration": 8.4},
    {"scene_id": 2, "gcs_uri": "gs://docureel/clips/scene2.mp4", "duration": 7.7}
  ]
}
```

---

### [6] StitcherAgent → `session["final_video_uri"]`
Captions are generated as a pure function from TTS word timestamps — no LLM needed:

```python
def timestamps_to_srt(word_timestamps):
    srt = []
    for i, word in enumerate(word_timestamps):
        start = format_time(word["start"])
        end = format_time(word["end"])
        srt.append(f"{i+1}\n{start} --> {end}\n{word['word']}\n")
    return "\n".join(srt)
```

---

### [6] StitcherAgent → `session["final_video_uri"]`
ffmpeg command logic:
1. Concatenate Veo clips in scene order
2. Overlay TTS audio track
3. Burn in captions from SRT (generated from TTS word timestamps — pure function)
4. Output 1080x1920 (vertical, TikTok format)
5. Upload to GCS → return signed URL to frontend

```json
{
  "final_video_uri": "https://storage.googleapis.com/docureel/final/session_abc.mp4",
  "duration_seconds": 43.2,
  "format": "1080x1920 vertical MP4"
}
```

---

### [7] LiveAgent — Always On
```
Model: Gemini Live API
System Prompt:
  "You are a concise analyst for this report: {manifest}.
   Answer questions directly. Use stats from the report.
   Always end your answer with: resuming now"

Behavior:
  - WebSocket open from page load
  - Sits idle while video plays
  - User speaks → frontend sends PAUSE signal + audio stream
  - Agent answers in voice
  - "resuming now" detected → frontend sends RESUME signal
```

---

## GCP Infrastructure

```
Cloud Storage (GCS)
├── /uploads          ← raw PDFs
├── /audio            ← TTS wav files  
├── /clips            ← Veo scene clips
└── /final            ← stitched output videos

Cloud Run
├── /api              ← FastAPI: orchestrates ADK pipeline
├── /live             ← WebSocket: Gemini Live Agent (session affinity ON)
└── /stitch           ← ffmpeg worker

Vertex AI
├── Gemini 2.0 Flash  ← parser, scriptwriter, video script, captions
├── Veo 2             ← video clip generation
└── Gemini Live API   ← real-time voice agent

Firebase Hosting
└── React frontend    ← video player + mic UI
```

---

## Team Split

| Person | Owns | Key Output |
|--------|------|------------|
| **Person 1** | ADK root wiring + ParserAgent + GCP infra | `manifest` + pipeline running |
| **Person 2** | NarrativeScriptAgent + VideoScriptAgent | `narration_script` + `video_script` |
| **Person 3** | TTSAgent + VeoAgent + StitcherAgent (ffmpeg) | `tts_result` + `veo_clips` + `final_video_uri` |
| **Person 4** | Frontend + LiveAgent WebSocket + pause/resume | Working demo UI |

---

## Execution Order (5-7 Hours)

| Time | Milestone |
|------|-----------|
| 0:00 | GCS bucket live. PDF upload endpoint working. |
| 1:00 | ParserAgent returns clean manifest JSON |
| 1:30 | NarrativeScriptAgent returns script |
| 2:00 | TTSAgent returns audio + timestamps |
| 2:30 | VideoScriptAgent returns Veo prompts |
| 3:00 | First Veo clip generated (fire these early — they're slow) |
| 3:30 | ffmpeg stitch working on dummy clips |
| 4:00 | Frontend plays a video end-to-end |
| 5:00 | Live Agent answers one question |
| 5:30 | Pause/resume working |
| 6:00 | Full demo rehearsed on a real corporate report PDF |

---

## The Demo Moment

> Upload a 30-page Q3 earnings report.
> 45 seconds later: a punchy, cinematic TikTok plays.
> Mid-video: *"Wait — why did North America underperform?"*
> Video pauses. Agent: *"NA revenue fell 11% due to rising interest rates
> compressing enterprise software budgets in H2. Resuming now."*
> Video continues.

**That's your winner.**
