# WS /api/live/{job_id}
# LiveAgent — always-on WebSocket for real-time voice Q&A mid-playback
# - Loads session["manifest"] from job_store as system context
# - Receives: raw PCM 16-bit audio bytes from frontend
# - Sends:    { type: "transcript", text: str }
# - Frontend detects "resuming now" in text → resumes video playback
# Model: Gemini Live API
