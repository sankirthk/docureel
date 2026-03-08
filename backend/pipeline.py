from google.adk.agents import SequentialAgent
from agents.parser import parser_agent
from agents.narrative_script import narrative_script_agent
from agents.tts import tts_agent
from agents.video_script import video_script_agent
from agents.veo import veo_agent
from agents.stitcher import stitcher_agent
from tools.job_store import update_job
import traceback

# Root pipeline — flat sequential, no unnecessary wrappers
pipeline = SequentialAgent(
    name="NeverRTFM",
    sub_agents=[
        parser_agent,           # PDF → manifest
        narrative_script_agent, # manifest → narration_script
        tts_agent,              # narration_script → tts_result
        video_script_agent,     # narration_script + tts_result → video_script
        veo_agent,              # video_script → veo_clips
        stitcher_agent,         # everything → final_video_uri
    ]
)

async def run_pipeline(job_id: str, file_path: str):
    """Entry point called by the FastAPI background task."""
    try:
        update_job(job_id, status="processing", step="parsing")

        # ADK session state — passed through all agents
        session_state = {
            "job_id": job_id,
            "file_path": file_path,
        }

        # Run the pipeline
        result = await pipeline.run_async(
            input=f"Process the PDF at: {file_path}",
            state=session_state
        )

        update_job(
            job_id,
            status="done",
            step="complete",
            video_url=session_state.get("final_video_uri"),
            manifest=session_state.get("manifest"),
        )

    except Exception as e:
        update_job(
            job_id,
            status="error",
            error=str(e),
            traceback=traceback.format_exc()
        )
