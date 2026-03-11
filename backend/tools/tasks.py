"""
Cloud Tasks helper — enqueue a pipeline run.

Required env vars (prod):
  CLOUD_TASKS_QUEUE  — full queue path: projects/P/locations/L/queues/Q
  SERVICE_URL        — Cloud Run service URL: https://xxx.run.app
  INTERNAL_SECRET    — shared secret checked by the worker endpoint

If CLOUD_TASKS_QUEUE or SERVICE_URL are not set (local dev), returns False
and the caller falls back to a FastAPI background task.
"""

import json
import os

CLOUD_TASKS_QUEUE = os.getenv("CLOUD_TASKS_QUEUE", "")
SERVICE_URL = os.getenv("SERVICE_URL", "")
INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "")


def enqueue_pipeline(job_id: str, file_path: str, pdf_hash: str, tone: str) -> bool:
    """
    Enqueue a pipeline run via Cloud Tasks. Returns True if enqueued,
    False if Cloud Tasks is not configured (caller falls back to background task).
    """
    if not CLOUD_TASKS_QUEUE or not SERVICE_URL:
        return False

    from google.cloud import tasks_v2
    from google.protobuf import duration_pb2

    client = tasks_v2.CloudTasksClient()
    payload = json.dumps({
        "job_id": job_id,
        "file_path": file_path,
        "pdf_hash": pdf_hash,
        "tone": tone,
    }).encode()

    task = tasks_v2.Task(
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=f"{SERVICE_URL}/internal/run-pipeline",
            headers={
                "Content-Type": "application/json",
                "X-Internal-Secret": INTERNAL_SECRET,
            },
            body=payload,
        ),
        dispatch_deadline=duration_pb2.Duration(seconds=1800),  # 30 min
    )

    client.create_task(request={"parent": CLOUD_TASKS_QUEUE, "task": task})
    print(f"[tasks] Enqueued pipeline for job {job_id} via Cloud Tasks", flush=True)
    return True
