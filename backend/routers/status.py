# GET /api/status/{job_id}
# Reads job from tools/job_store.py
# Returns: { status: "processing"|"done"|"error", step: str, video_url: str|null }
