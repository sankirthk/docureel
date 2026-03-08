import hashlib
import traceback

from google.adk.agents import SequentialAgent, ParallelAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.parser import parser_agent
from agents.knowledge_base import knowledge_base_agent
from agents.video_script import video_script_agent
from agents.veo import veo_agent
from agents.stitcher import stitcher_agent
from tools.job_store import update_job, get_job
from tools.storage import load_cache, save_cache

APP_NAME = "nevertrtfm"

def _build_full_pipeline():
    ingestion = ParallelAgent(
        name="Ingestion",
        sub_agents=[parser_agent, knowledge_base_agent],
    )
    return SequentialAgent(
        name="NeverRTFM",
        sub_agents=[ingestion, video_script_agent, veo_agent, stitcher_agent],
    )


def _build_video_only_pipeline():
    return SequentialAgent(
        name="NeverRTFM_VideoOnly",
        sub_agents=[veo_agent, stitcher_agent],
    )


async def run_pipeline(job_id: str, file_path: str, pdf_bytes: bytes):
    """Entry point called by the FastAPI background task."""
    try:
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
        print(f"\n[pipeline] ▶ Starting pipeline for job {job_id}", flush=True)
        print(f"[pipeline]   file: {file_path}  pdf_hash: {pdf_hash[:16]}...", flush=True)

        # Check cache — fastest path first
        cached_final = load_cache(pdf_hash, "final_video")
        if cached_final and cached_final.get("uri"):
            final_uri = cached_final["uri"]
            from pathlib import Path
            if final_uri.startswith("/") and not Path(final_uri).exists():
                print(f"[pipeline] ⚠ Cached final video missing from disk, re-generating", flush=True)
                cached_final = None

        if cached_final and cached_final.get("uri"):
            final_uri = cached_final["uri"]
            print(f"[pipeline] ⚡ Full cache hit — returning existing video instantly", flush=True)
            print(f"[pipeline]   uri: {final_uri}", flush=True)
            cached_manifest = load_cache(pdf_hash, "manifest")
            update_job(job_id, status="done", step="complete",
                       video_url=final_uri, final_video_uri=final_uri,
                       manifest=cached_manifest)
            return

        cached_manifest = load_cache(pdf_hash, "manifest")
        cached_video_script = load_cache(pdf_hash, "video_script")
        cache_hit = cached_manifest is not None and cached_video_script is not None

        if cache_hit:
            print(f"[pipeline] ⚡ Cache hit — skipping parse + script, jumping to Veo", flush=True)
            agent = _build_video_only_pipeline()
            initial_step = "veo"
        else:
            print(f"[pipeline]   No cache — running full pipeline", flush=True)
            agent = _build_full_pipeline()
            initial_step = "parsing"

        update_job(job_id, status="processing", step=initial_step)

        session_service = InMemorySessionService()

        initial_state = {
            "job_id": job_id,
            "file_path": file_path,
            "pdf_hash": pdf_hash,
        }
        if cache_hit:
            initial_state["manifest"] = cached_manifest
            initial_state["video_script"] = cached_video_script
            print(f"[pipeline]   Loaded manifest ({len(cached_manifest.get('key_sections', []))} sections) and video_script ({len(cached_video_script.get('scenes', []))} scenes) from cache", flush=True)

        # Create a session with initial state — agents read/write via ctx.session.state
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=job_id,
            session_id=job_id,
            state=initial_state,
        )

        runner = Runner(
            agent=agent,
            app_name=APP_NAME,
            session_service=session_service,
        )

        # Drain the event stream — agents update job_store internally as they run
        async for event in runner.run_async(
            user_id=job_id,
            session_id=job_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=f"Process the PDF at: {file_path}")],
            ),
        ):
            if event.content:
                print(f"  [{event.author}] {event.content}")

        # Read final state from session
        final_session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=job_id,
            session_id=job_id,
        )
        state = final_session.state

        # Session state may not reflect agent writes (ADK InMemorySessionService quirk),
        # so fall back to the job store where StitcherAgent writes directly.
        final_uri = state.get("final_video_uri") or (get_job(job_id) or {}).get("final_video_uri")
        if final_uri:
            save_cache(pdf_hash, "final_video", {"uri": final_uri})
            print(f"[pipeline]   Cached final video for future runs", flush=True)

        print(f"\n[pipeline] ✅ Pipeline complete for job {job_id}", flush=True)
        print(f"[pipeline]   final_video_uri: {final_uri}", flush=True)
        update_job(
            job_id,
            status="done",
            step="complete",
            video_url=final_uri,
            manifest=state.get("manifest"),
            knowledge_base=state.get("knowledge_base"),
            veo_clips=state.get("veo_clips"),
            final_video_uri=final_uri,
        )

    except Exception as e:
        print(f"\n[pipeline] ❌ Pipeline FAILED for job {job_id}", flush=True)
        print(f"[pipeline]   error: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        update_job(
            job_id,
            status="error",
            error=str(e),
            traceback=traceback.format_exc(),
        )
