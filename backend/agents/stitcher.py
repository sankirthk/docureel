# StitcherAgent
# IN:  session["veo_clips"]   — clip GCS URIs in scene order
#      session["tts_result"]  — audio_gcs_uri + word_timestamps for captions
# OUT: session["final_video_uri"]  — signed GCS URL to finished MP4
# Tool: ffmpeg
# Steps: concatenate clips → overlay audio → burn SRT captions → output 1080x1920 vertical MP4
# Captions: generated as pure function from word_timestamps (no LLM)
