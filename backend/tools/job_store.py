"""
Job store — always Firestore.

For local dev, either:
  - Set FIRESTORE_EMULATOR_HOST=localhost:8080 and run the emulator
  - Or point to a real GCP project with GOOGLE_CLOUD_PROJECT set

Job shape:
{
    "job_id":       str,
    "status":       "processing" | "done" | "error",
    "step":         str,
    "video_url":    str | None,   # gs:// URI of final video
    "manifest":     dict | None,
    "knowledge_base": dict | None,
    "error":        str | None,
}
"""

import os

_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
_COLLECTION = "jobs"

_db_client = None

def _db():
    global _db_client
    if _db_client is None:
        from google.cloud import firestore
        _db_client = firestore.Client(project=_PROJECT)
    return _db_client


def create_job(job_id: str) -> dict:
    job = {
        "job_id": job_id,
        "status": "processing",
        "step": "queued",
        "video_url": None,
        "manifest": None,
        "knowledge_base": None,
        "error": None,
    }
    _db().collection(_COLLECTION).document(job_id).set(job)
    return job


def get_job(job_id: str) -> dict | None:
    snap = _db().collection(_COLLECTION).document(job_id).get()
    return snap.to_dict() if snap.exists else None


def update_job(job_id: str, **kwargs):
    _db().collection(_COLLECTION).document(job_id).set(kwargs, merge=True)
