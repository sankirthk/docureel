"""
GET /api/status/{job_id}  → { status, step, video_url }
GET /api/video/{job_id}   → FileResponse (DEV_MODE only)

video_url is always a fresh signed GCS URL generated on every status call
so it never expires from the user's perspective. The gs:// URI is what gets
stored in Firestore — signing happens here, not in the pipeline.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from tools.auth import require_token
from tools.limiter import limiter
from tools.job_store import get_job
from tools.storage import DEV_MODE, get_signed_url

router = APIRouter()


def _resolve_video_url(job_id: str, raw_url: str | None) -> str | None:
    """Return a browser-accessible URL for the final video.

    prod: raw_url is gs:// — sign fresh on every call so it never expires.
    dev:  raw_url is a local path — serve via /api/video/{job_id}.
    """
    if not raw_url:
        return None
    if raw_url.startswith("gs://"):
        return get_signed_url(raw_url)
    if raw_url.startswith("http"):
        return raw_url  # already a URL (legacy / fallback)
    # Local filesystem path (DEV_MODE)
    return f"http://127.0.0.1:8080/api/video/{job_id}"


@router.get("/status/{job_id}")
@limiter.limit("60/minute")
async def status(request: Request, job_id: str, _: None = Depends(require_token)):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "step": job["step"],
        "video_url": _resolve_video_url(job_id, job.get("video_url")),
        "error": job.get("error"),
    }


@router.get("/video/{job_id}")
async def video(job_id: str):
    """Serve the final video file. Only meaningful in DEV_MODE."""
    job = get_job(job_id)
    if job is None or job.get("status") != "done":
        raise HTTPException(status_code=404, detail="Video not ready.")

    raw_url = job.get("video_url") or job.get("final_video_uri")
    if not raw_url:
        raise HTTPException(status_code=404, detail="No video URL in job.")

    if raw_url.startswith("http"):
        return RedirectResponse(raw_url)

    # DEV_MODE: raw_url is a local absolute path
    return FileResponse(raw_url, media_type="video/mp4")
