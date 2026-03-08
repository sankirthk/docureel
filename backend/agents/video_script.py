# VideoScriptAgent
# IN:  session["narration_script"]  — scenes with narration text
#      session["tts_result"]        — scene_timestamps for time alignment
# OUT: session["video_script"]      — { veo_prompts: [{ scene_id, start, end, prompt, style }] }
# Model: Gemini 2.0 Flash
