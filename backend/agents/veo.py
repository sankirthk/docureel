# VeoAgent
# IN:  session["video_script"]  — veo_prompts per scene with timing
# OUT: session["veo_clips"]     — { clips: [{ scene_id, gcs_uri, duration }] }
# Model: Veo 2 via Vertex AI
# Note: Veo generation is slow — kick off all clips in parallel
