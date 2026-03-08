# POST /api/generate
# Body: multipart/form-data { file: PDF }
# - Saves PDF via storage.py
# - Creates a job entry in job_store
# - Kicks off agents/pipeline.py run_pipeline() as a FastAPI background task
# Returns: { job_id: str, status: "processing" }
