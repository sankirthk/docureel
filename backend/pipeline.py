import hashlib
import traceback

from google.adk.agents import SequentialAgent, ParallelAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.parser import ParserAgent
from agents.knowledge_base import KnowledgeBaseAgent
from agents.video_script import VideoScriptAgent
from agents.veo import VeoAgent
from agents.stitcher import StitcherAgent
from tools.job_store import update_job, get_job
from tools.storage import load_cache, save_cache

APP_NAME = "nevertrtfm"


def _build_full_pipeline():
    """
    ParserAgent + KnowledgeBaseAgent run truly in parallel via ParallelAgent.
    Both now use asyncio.to_thread internally so the event loop is not blocked.
    Fresh agent instances every call — ADK sets a parent pointer that prevents reuse.
    """
    ingestion = ParallelAgent(
        name="Ingestion",
        sub_agents=[
            ParserAgent(name="ParserAgent"),
            KnowledgeBaseAgent(name="KnowledgeBaseAgent"),
        ],
    )
    return SequentialAgent(
        name="NeverRTFM",
        sub_agents=[
            ingestion,
            VideoScriptAgent(name="VideoScriptAgent"),
            VeoAgent(name="VeoAgent"),
            StitcherAgent(name="StitcherAgent"),
        ],
    )


def _build_veo_only_pipeline():
    return SequentialAgent(
        name="NeverRTFM_VeoOnly",
        sub_agents=[VeoAgent(name="VeoAgent"), StitcherAgent(name="StitcherAgent")],
    )


async def run_pipeline(job_id: str, file_path: str, pdf_bytes: bytes):
    """Entry point called by the FastAPI background task."""
    try:
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
        print(f"\n[pipeline] ▶ Starting pipeline for job {job_id}", flush=True)
        print(f"[pipeline]   file: {file_path}  pdf_hash: {pdf_hash[:16]}...", flush=True)

        # ── Full cache hit: return existing video immediately ──────────────────
        cached_final = load_cache(pdf_hash, "final_video")
        if cached_final and cached_final.get("uri"):
            from pathlib import Path
            uri = cached_final["uri"]
            if uri.startswith("/") and not Path(uri).exists():
                print(f"[pipeline] ⚠ Cached final video missing from disk, re-generating", flush=True)
                cached_final = None

        if cached_final and cached_final.get("uri"):
            print(f"[pipeline] ⚡ Full cache hit — done instantly", flush=True)
            update_job(job_id, status="done", step="complete",
                       video_url=cached_final["uri"], final_video_uri=cached_final["uri"],
                       manifest=load_cache(pdf_hash, "manifest"))
            return

        cached_manifest = load_cache(pdf_hash, "manifest")
        cached_video_script = load_cache(pdf_hash, "video_script")
        has_script_cache = cached_manifest is not None and cached_video_script is not None

        if has_script_cache:
            print(f"[pipeline] ⚡ Script cache hit — skipping ingestion, jumping to Veo", flush=True)
            agent = _build_veo_only_pipeline()
            initial_step = "veo"
        else:
            print(f"[pipeline]   No cache — running full pipeline (Parser ∥ KnowledgeBase → VideoScript → Veo [all presenter] → Stitcher)", flush=True)
            agent = _build_full_pipeline()
            initial_step = "parsing"

        update_job(job_id, status="processing", step=initial_step)

        session_service = InMemorySessionService()
        initial_state: dict = {
            "job_id": job_id,
            "file_path": file_path,
            "pdf_hash": pdf_hash,
        }
        if has_script_cache:
            initial_state["manifest"] = cached_manifest
            initial_state["video_script"] = cached_video_script
            print(f"[pipeline]   Loaded manifest + video_script ({len(cached_video_script.get('scenes', []))} scenes) from cache", flush=True)

        await session_service.create_session(
            app_name=APP_NAME,
            user_id=job_id,
            session_id=job_id,
            state=initial_state,
        )

        runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

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

        # ── Finalise ───────────────────────────────────────────────────────────
        final_session = await session_service.get_session(
            app_name=APP_NAME, user_id=job_id, session_id=job_id,
        )
        state = final_session.state

        final_uri = state.get("final_video_uri") or (get_job(job_id) or {}).get("final_video_uri")
        if final_uri:
            save_cache(pdf_hash, "final_video", {"uri": final_uri})

        print(f"\n[pipeline] ✅ Complete — final_uri: {final_uri}", flush=True)
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
