# In-memory job store
# Swap for Firestore in production
#
# Job shape:
# {
#   "job_id":    str,
#   "status":    "processing" | "done" | "error",
#   "step":      str,           — current pipeline step name
#   "video_url": str | None,    — signed URL set by StitcherAgent
#   "manifest":  dict | None,   — set on completion for LiveAgent context
#   "error":     str | None,
# }
#
# Functions to implement:
#   create_job(job_id) -> dict
#   get_job(job_id) -> dict | None
#   update_job(job_id, **kwargs)
