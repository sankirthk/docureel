"""
Job store — Firestore in prod, in-memory fallback for local dev.

Job shape:
{
    "job_id":       str,
    "status":       "processing" | "done" | "error",
    "step":         str,        # current pipeline step
    "video_url":    str | None, # signed URL set by StitcherAgent
    "manifest":     dict | None,
    "knowledge_base": dict | None,
    "error":        str | None,
}
"""

import os
import threading

_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
_COLLECTION = "jobs"

# ---------------------------------------------------------------------------
# In-memory fallback (local dev / no GOOGLE_CLOUD_PROJECT set)
# ---------------------------------------------------------------------------
_store: dict[str, dict] = {}
_lock = threading.Lock()


def _use_firestore() -> bool:
    return bool(_PROJECT)


_db_client = None
_db_lock = threading.Lock()

def _db():
    global _db_client
    if _db_client is None:
        with _db_lock:
            if _db_client is None:
                from google.cloud import firestore
                _db_client = firestore.Client(project=_PROJECT)
    return _db_client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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
    if _use_firestore():
        _db().collection(_COLLECTION).document(job_id).set(job)
    else:
        with _lock:
            _store[job_id] = job
    return job


def get_job(job_id: str) -> dict | None:
    if _use_firestore():
        snap = _db().collection(_COLLECTION).document(job_id).get()
        return snap.to_dict() if snap.exists else None
    with _lock:
        return _store.get(job_id)


def update_job(job_id: str, **kwargs):
    if _use_firestore():
        # set(merge=True) creates the doc if missing and merges fields
        _db().collection(_COLLECTION).document(job_id).set(kwargs, merge=True)
    else:
        with _lock:
            if job_id in _store:
                _store[job_id].update(kwargs)
