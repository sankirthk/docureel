# WS /api/live/{job_id} — LiveAgent
# Bidirectional: receives PCM 16-bit audio from browser, sends text transcripts back.
# "resuming now" in response text → frontend resumes video (no backend logic needed).

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.genai import types

from tools.gemini import build_client
from tools.job_store import get_job

router = APIRouter()

LIVE_MODEL = "gemini-2.0-flash-live-preview-04-09"


def _build_system_prompt(job: dict) -> str:
    manifest = job.get("manifest") or {}
    knowledge_base = job.get("knowledge_base") or {}

    lines = [
        f"You are a helpful assistant answering questions about a report titled: \"{manifest.get('title', 'this report')}\".",
        "",
        f"OVERALL SUMMARY: {manifest.get('overall_summary', '')}",
        f"SENTIMENT: {manifest.get('sentiment', '')} — {manifest.get('sentiment_reason', '')}",
        "",
        "KEY SECTIONS:",
    ]

    for section in manifest.get("key_sections", []):
        lines.append(f"\n[{section.get('heading', '')}]")
        lines.append(f"Summary: {section.get('summary', '')}")
        for stat in section.get("key_stats", []):
            lines.append(f"  • {stat}")

    if knowledge_base:
        lines.append("\nDETAILED KNOWLEDGE BASE:")

        for finding in knowledge_base.get("deep_findings", []):
            lines.append(f"  - {finding}")

        for fact in knowledge_base.get("key_facts", []):
            lines.append(f"  - {fact}")

        for risk in knowledge_base.get("risks_and_failures", []):
            lines.append(f"  ⚠ {risk}")

        for success in knowledge_base.get("successes_and_rationale", []):
            lines.append(f"  ✓ {success}")

        definitions = knowledge_base.get("definitions", {})
        if isinstance(definitions, dict):
            for term, definition in definitions.items():
                lines.append(f"  [{term}]: {definition}")

        expert = knowledge_base.get("expert_detail", "")
        if expert:
            lines.append(f"\nEXPERT DETAIL: {expert}")

    lines.append(
        "\nIMPORTANT: Answer questions conversationally, like explaining to a friend. "
        "Be concise (2-4 sentences max). "
        "Always end every answer with the exact phrase \"resuming now\" so the video can resume."
    )

    return "\n".join(lines)


@router.websocket("/live/{job_id}")
async def live(websocket: WebSocket, job_id: str):
    job = get_job(job_id)
    if job is None or job["status"] != "done":
        await websocket.close(code=1008)
        return

    await websocket.accept()

    system_prompt = _build_system_prompt(job)
    client = build_client()

    try:
        async with client.aio.live.connect(
            model=LIVE_MODEL,
            config={
                "response_modalities": ["TEXT"],
                "system_instruction": system_prompt,
            },
        ) as session:

            async def receive_from_client():
                """Read PCM audio bytes from browser → forward to Gemini."""
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        await session.send_realtime_input(
                            media=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
                        )
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    print(f"[live] receive_from_client error: {e}")

            async def send_to_client():
                """Read Gemini text responses → forward to browser as JSON."""
                try:
                    while True:
                        async for msg in session.receive():
                            if msg.text:
                                await websocket.send_json(
                                    {"type": "transcript", "text": msg.text}
                                )
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    print(f"[live] send_to_client error: {e}")

            receive_task = asyncio.create_task(receive_from_client())
            send_task = asyncio.create_task(send_to_client())

            done, pending = await asyncio.wait(
                [receive_task, send_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[live] session error for job {job_id}: {e}")
        try:
            await websocket.send_json({"type": "error", "text": str(e)})
            await websocket.close()
        except Exception:
            pass
