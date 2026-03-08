# Storage abstraction — local dev vs GCS
# Controlled by DEV_MODE env var (default: true)
#
# DEV_MODE=true  → files written to local_storage/{job_id}/
# DEV_MODE=false → files written to GCS bucket (GCS_BUCKET env var)
#                  GCS paths: /uploads, /audio, /clips, /final
#
# Functions to implement:
#   save_upload(job_id, filename, data: bytes) -> str   (local path or gs:// URI)
#   get_uri(job_id, filename) -> str
#   get_signed_url(gcs_uri) -> str                      (prod only, for final video)
