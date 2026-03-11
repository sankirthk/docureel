"""
GET /api/status/{job_id}  → { status, step, video_url }
GET /api/video/{job_id}   → FileResponse (DEV_MODE only)

video_url: the status endpoint returns a signed GCS URL. It caches the
signed URL + expiry in the job record and re-signs only when < 30 min
of validity remains, avoiding an IAM round-trip on every poll.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from tools.auth import require_token
from tools.limiter import limiter
from tools.job_store import get_job, update_job
from tools.storage import DEV_MODE, get_signed_url

router = APIRouter()

# Re-sign when less than this much validity remains
_RESIGN_THRESHOLD = 30 * 60  # 30 minutes


def _resolve_video_url(job_id: str, job: dict) -> str | None:
    raw_url = job.get("video_url")
    if not raw_url:
        return None

    # DEV_MODE: local path → serve via /api/video/
    if not raw_url.startswith("gs://"):
        if raw_url.startswith("http"):
            return raw_url
        return f"http://127.0.0.1:8080/api/video/{job_id}"

    # Prod: check cached signed URL
    cached_signed = job.get("video_url_signed")
    cached_expiry = job.get("video_url_expires_at", 0.0)

    if cached_signed and (cached_expiry - time.time()) > _RESIGN_THRESHOLD:
        return cached_signed

    # Sign fresh (access-token based, valid ~1 hour)
    signed = get_signed_url(raw_url)
    expires_at = time.time() + 3600  # conservative 1hr
    update_job(job_id, video_url_signed=signed, video_url_expires_at=expires_at)
    return signed


@router.get("/status/{job_id}")
@limiter.limit("60/minute")
async def status(request: Request, job_id: str, _: None = Depends(require_token)):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id":    job["job_id"],
        "status":    job["status"],
        "step":      job["step"],
        "video_url": _resolve_video_url(job_id, job),
        "error":     job.get("error"),
    }


@router.get("/video/{job_id}")
async def video(job_id: str):
    """Serve the final video file. DEV_MODE only."""
    job = get_job(job_id)
    if job is None or job.get("status") != "done":
        raise HTTPException(status_code=404, detail="Video not ready.")

    raw_url = job.get("video_url") or job.get("final_video_uri")
    if not raw_url:
        raise HTTPException(status_code=404, detail="No video URL in job.")

    if raw_url.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(raw_url)

    return FileResponse(raw_url, media_type="video/mp4")
