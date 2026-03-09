"""
GET /api/status/{job_id}  → { status, step, video_url }
GET /api/video/{job_id}   → FileResponse (DEV_MODE) or redirect (prod signed URL)

In DEV_MODE the stitcher saves final.mp4 as a local path. The status endpoint
rewrites that to /api/video/{job_id} so the browser has an actual HTTP URL.
In prod the stitcher stores a signed GCS URL which is returned as-is.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from tools.auth import require_token
from tools.limiter import limiter
from tools.job_store import get_job
from tools.storage import DEV_MODE

router = APIRouter()


def _resolve_video_url(job_id: str, raw_url: str | None) -> str | None:
    """Return a browser-accessible URL for the final video."""
    if not raw_url:
        return None
    if raw_url.startswith("http"):
        return raw_url          # signed GCS URL — already usable
    if raw_url.startswith("gs://"):
        return None             # unsigned GCS URI — shouldn't happen in prod
    # Local filesystem path (DEV_MODE) — serve via /api/video/{job_id}
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
