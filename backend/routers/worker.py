"""
POST /internal/run-pipeline

Called by Cloud Tasks to execute the pipeline for a job.
Secured by X-Internal-Secret header.
"""

import os

from fastapi import APIRouter, Header, HTTPException, Request

INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "")

router = APIRouter()


@router.post("/internal/run-pipeline")
async def run_pipeline_worker(
    request: Request,
    x_internal_secret: str = Header(default=""),
):
    if INTERNAL_SECRET and x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden.")

    body = await request.json()
    job_id = body["job_id"]
    file_path = body["file_path"]
    pdf_hash = body["pdf_hash"]
    tone = body.get("tone", "explanatory")

    print(f"[worker] ▶ Cloud Tasks triggered pipeline for job {job_id}", flush=True)

    from pipeline import run_pipeline
    await run_pipeline(job_id, file_path, pdf_hash, tone)

    return {"ok": True}
