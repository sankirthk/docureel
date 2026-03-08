"""
Storage abstraction — local dev vs GCS.

DEV_MODE=true  → files written to local_storage/{job_id}/
DEV_MODE=false → files written to GCS (GCS_BUCKET env var)
"""

import json
import os
from pathlib import Path

DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"
GCS_BUCKET = os.getenv("GCS_BUCKET", "nevertrtfm")

LOCAL_ROOT = Path(__file__).parent.parent / "local_storage"


CACHE_ROOT = LOCAL_ROOT / "cache"


def save_cache(pdf_hash: str, name: str, data: dict) -> None:
    """Persist a dict as JSON under local_storage/cache/{pdf_hash}/{name}.json"""
    dest = CACHE_ROOT / pdf_hash / f"{name}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2))


def load_cache(pdf_hash: str, name: str) -> dict | None:
    """Load a cached JSON dict, or return None if not found."""
    path = CACHE_ROOT / pdf_hash / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def read_bytes(uri: str) -> bytes:
    """Read bytes from a local path or a gs:// URI."""
    if uri.startswith("gs://"):
        client = build_gcs_client()
        without_prefix = uri.removeprefix("gs://")
        bucket_name, blob_path = without_prefix.split("/", 1)
        return client.bucket(bucket_name).blob(blob_path).download_as_bytes()
    with open(uri, "rb") as f:
        return f.read()


def build_gcs_client():
    from google.cloud import storage
    return storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT"))


def save_upload(job_id: str, filename: str, data: bytes) -> str:
    """Save job-scoped bytes and return a URI (local path or gs://)."""
    if DEV_MODE:
        dest = LOCAL_ROOT / job_id / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)
    else:
        return _gcs_upload(job_id, filename, data)


def save_shared(path: str, data: bytes) -> str:
    """
    Save shared (non-job-scoped) bytes under shared/{path}.
    Used for assets like avatars that are reused across all jobs.
    Returns a URI (local path or gs://).
    """
    if DEV_MODE:
        dest = LOCAL_ROOT / "shared" / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)
    else:
        client = build_gcs_client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(f"shared/{path}")
        blob.upload_from_string(data)
        return f"gs://{GCS_BUCKET}/shared/{path}"


def get_uri(job_id: str, filename: str) -> str:
    """Return the URI for an already-saved file."""
    if DEV_MODE:
        return str(LOCAL_ROOT / job_id / filename)
    else:
        return f"gs://{GCS_BUCKET}/{job_id}/{filename}"


def get_signed_url(gcs_uri: str) -> str:
    """Return a signed HTTPS URL for a GCS object (prod only)."""
    client = build_gcs_client()
    # gcs_uri format: gs://bucket/path/to/file
    without_prefix = gcs_uri.removeprefix("gs://")
    bucket_name, blob_path = without_prefix.split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    return blob.generate_signed_url(expiration=3600, method="GET", version="v4")


def _gcs_upload(job_id: str, filename: str, data: bytes) -> str:
    client = build_gcs_client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(f"{job_id}/{filename}")
    blob.upload_from_string(data)
    return f"gs://{GCS_BUCKET}/{job_id}/{filename}"
