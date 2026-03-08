"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  FileText,
  Loader2,
  Mic,
  Pause,
  Play,
  Square,
  UploadCloud,
  Volume2,
} from "lucide-react";
import { PCMPlayer } from "../lib/pcm-player";
import { MicStreamer } from "../lib/mic-stream";

type JobState = "idle" | "uploading" | "processing" | "done" | "error";

type TranscriptLine = {
  speaker: "user" | "agent";
  text: string;
  final: boolean;
};

const API_BASE = "http://127.0.0.1:8080/api";

function wsUrlForJob(jobId: string) {
  const base =
    typeof window !== "undefined"
      ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8080`
      : "ws://127.0.0.1:8080";

  return `${base}/api/live/${jobId}`;
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobState, setJobState] = useState<JobState>("idle");
  const [statusText, setStatusText] = useState("Upload a PDF to begin.");
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  const [liveConnected, setLiveConnected] = useState(false);
  const [isMicActive, setIsMicActive] = useState(false);
  const [isUserSpeaking, setIsUserSpeaking] = useState(false);
  const [isAgentSpeaking, setIsAgentSpeaking] = useState(false);

  const [sceneText, setSceneText] = useState(
    "Naive kernel fusion caused a 30x slowdown."
  );
  const [question, setQuestion] = useState(
    "Why did kernel fusion slow down so much?"
  );

  const [transcripts, setTranscripts] = useState<TranscriptLine[]>([]);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<number | null>(null);
  const micRef = useRef<MicStreamer | null>(null);

  const player = useMemo(() => new PCMPlayer(24000), []);

  function pushTranscript(next: TranscriptLine) {
    setTranscripts((prev) => {
      if (prev.length > 0) {
        const last = prev[prev.length - 1];
        if (
          last.speaker === next.speaker &&
          !last.final &&
          !next.final
        ) {
          const copy = [...prev];
          copy[copy.length - 1] = next;
          return copy;
        }

        if (
          last.speaker === next.speaker &&
          !last.final &&
          next.final
        ) {
          const copy = [...prev];
          copy[copy.length - 1] = next;
          return copy;
        }
      }
      return [...prev, next];
    });
  }

  async function handleUpload() {
    if (!file) return;

    setJobState("uploading");
    setStatusText("Uploading PDF...");
    setVideoUrl(null);
    setJobId(null);
    setTranscripts([]);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Upload failed: ${res.status}`);
      }

      const data = await res.json();
      setJobId(data.job_id);
      setJobState("processing");
      setStatusText("Processing report and generating video...");
    } catch (err) {
      console.error(err);
      setJobState("error");
      setStatusText("Upload failed.");
    }
  }

  useEffect(() => {
    if (!jobId || jobState !== "processing") return;

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/status/${jobId}`);
        if (!res.ok) return;

        const data = await res.json();

        if (data.status === "done") {
          setJobState("done");
          setStatusText("Generation complete.");
          if (data.video_url) {
            setVideoUrl(data.video_url);
          } else {
            setVideoUrl("https://www.w3schools.com/html/mov_bbb.mp4");
          }

          if (pollRef.current) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
        } else if (data.status === "error") {
          setJobState("error");
          setStatusText(data.error || "Generation failed.");

          if (pollRef.current) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
        } else {
          setStatusText(`Pipeline running: ${data.step ?? "processing"}...`);
        }
      } catch (err) {
        console.error(err);
      }
    };

    void poll();
    pollRef.current = window.setInterval(poll, 2000);

    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [jobId, jobState]);

  async function connectLive() {
    if (!jobId || wsRef.current) return;

    const ws = new WebSocket(wsUrlForJob(jobId));
    wsRef.current = ws;

    ws.onopen = () => {
      setLiveConnected(true);
      setStatusText("Live agent connected.");
    };

    ws.onclose = () => {
      setLiveConnected(false);
      setIsMicActive(false);
      setIsUserSpeaking(false);
      setIsAgentSpeaking(false);
      wsRef.current = null;
    };

    ws.onerror = (err) => {
      console.error("WebSocket error", err);
    };

    ws.onmessage = async (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "scene_updated") {
        return;
      }

      if (msg.type === "pause_video") {
        videoRef.current?.pause();
      }

      if (msg.type === "resume_video") {
        void videoRef.current?.play().catch(() => {});
      }

      if (msg.type === "audio") {
        if (!isUserSpeaking) {
          setIsAgentSpeaking(true);
          await player.playChunk(msg.data_b64);
        }
      }

      if (msg.type === "transcript") {
        if (msg.speaker === "agent") {
          setIsAgentSpeaking(!msg.final);
        }

        pushTranscript({
          speaker: msg.speaker,
          text: msg.text,
          final: Boolean(msg.final),
        });
      }

      if (msg.type === "error") {
        console.error("Live agent error:", msg.message);
        setStatusText(`Live error: ${msg.message}`);
      }
    };
  }

  async function sendSceneAndQuestion() {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    ws.send(
      JSON.stringify({
        type: "set_scene",
        scene_text: sceneText,
      })
    );

    setTimeout(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({
            type: "text",
            text: question,
          })
        );
      }
    }, 200);
  }

  async function startMic() {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    if (micRef.current) return;

    const mic = new MicStreamer({
      onPcmChunk: (chunk) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(chunk);
        }
      },
      onSpeechStart: () => {
        setIsUserSpeaking(true);
        setIsAgentSpeaking(false);
        player.stop();
        if (videoRef.current) {
          videoRef.current.pause();
        }
      },
      outputSampleRate: 16000,
    });

    await mic.start();
    micRef.current = mic;
    setIsMicActive(true);
    setStatusText("Microphone live. Start speaking.");
  }

  async function stopMic() {
    if (micRef.current) {
      await micRef.current.stop();
      micRef.current = null;
    }

    setIsMicActive(false);
    setIsUserSpeaking(false);

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "end_turn" }));
    }
  }

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
      }

      if (wsRef.current) {
        wsRef.current.close();
      }

      void player.close();
      void micRef.current?.stop();
    };
  }, [player]);

  return (
    <main className="min-h-screen bg-black text-white">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-10 flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-semibold tracking-tight">NeverRTFM</h1>
            <p className="mt-2 text-sm text-zinc-400">
              Upload any report. Get a short video. Ask questions live.
            </p>
          </div>
          <div className="rounded-full border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm text-zinc-300">
            {statusText}
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[420px_minmax(0,1fr)]">
          <section className="rounded-3xl border border-zinc-800 bg-zinc-950 p-6 shadow-2xl">
            <div className="mb-5 flex items-center gap-3">
              <div className="rounded-2xl bg-zinc-900 p-3">
                <UploadCloud className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-xl font-medium">Upload report</h2>
                <p className="text-sm text-zinc-400">PDF only</p>
              </div>
            </div>

            <label className="flex cursor-pointer flex-col items-center justify-center rounded-3xl border border-dashed border-zinc-700 bg-zinc-900/60 px-6 py-10 text-center hover:border-zinc-500">
              <FileText className="mb-3 h-8 w-8 text-zinc-300" />
              <span className="font-medium">Choose a PDF</span>
              <span className="mt-1 text-sm text-zinc-400">
                Drag and drop or browse
              </span>
              <input
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={(e) => {
                  const selected = e.target.files?.[0] ?? null;
                  setFile(selected);
                }}
              />
            </label>

            {file && (
              <div className="mt-4 rounded-2xl border border-zinc-800 bg-zinc-900 p-4 text-sm text-zinc-300">
                Selected: <span className="font-medium">{file.name}</span>
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={!file || jobState === "uploading" || jobState === "processing"}
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-white px-4 py-3 font-medium text-black transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {(jobState === "uploading" || jobState === "processing") && (
                <Loader2 className="h-4 w-4 animate-spin" />
              )}
              Generate video
            </button>

            <div className="mt-8">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
                Live Q&A controls
              </h3>

              <div className="space-y-3">
                <textarea
                  value={sceneText}
                  onChange={(e) => setSceneText(e.target.value)}
                  rows={3}
                  className="w-full rounded-2xl border border-zinc-800 bg-zinc-900 p-3 text-sm outline-none ring-0"
                  placeholder="Current scene text"
                />

                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  rows={3}
                  className="w-full rounded-2xl border border-zinc-800 bg-zinc-900 p-3 text-sm outline-none ring-0"
                  placeholder="Ask a question"
                />

                <button
                  onClick={connectLive}
                  disabled={!jobId || liveConnected === true}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm font-medium hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Volume2 className="h-4 w-4" />
                  {liveConnected ? "Live connected" : "Connect live agent"}
                </button>

                <button
                  onClick={sendSceneAndQuestion}
                  disabled={!liveConnected}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm font-medium hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Play className="h-4 w-4" />
                  Send scene + question
                </button>

                {!isMicActive ? (
                  <button
                    onClick={startMic}
                    disabled={!liveConnected}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-400 px-4 py-3 text-sm font-semibold text-black hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Mic className="h-4 w-4" />
                    Start talking
                  </button>
                ) : (
                  <button
                    onClick={stopMic}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-red-400 px-4 py-3 text-sm font-semibold text-black hover:opacity-90"
                  >
                    <Square className="h-4 w-4" />
                    Stop mic / end turn
                  </button>
                )}
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-3">
                  User speaking:{" "}
                  <span className={isUserSpeaking ? "text-emerald-400" : "text-zinc-400"}>
                    {isUserSpeaking ? "yes" : "no"}
                  </span>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-3">
                  Agent speaking:{" "}
                  <span className={isAgentSpeaking ? "text-sky-400" : "text-zinc-400"}>
                    {isAgentSpeaking ? "yes" : "no"}
                  </span>
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-3xl border border-zinc-800 bg-zinc-950 p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-medium">Video + live transcript</h2>
                <p className="text-sm text-zinc-400">
                  Agent audio plays here. User speech interrupts it immediately.
                </p>
              </div>
              <div className="rounded-full border border-zinc-800 bg-zinc-900 px-3 py-1 text-xs text-zinc-400">
                {jobState}
              </div>
            </div>

            <div className="overflow-hidden rounded-3xl border border-zinc-800 bg-black">
              {videoUrl ? (
                <video
                  ref={videoRef}
                  src={videoUrl}
                  controls
                  className="aspect-video w-full bg-black"
                />
              ) : (
                <div className="flex aspect-video items-center justify-center text-zinc-500">
                  Video will appear here after generation.
                </div>
              )}
            </div>

            <div className="mt-5 rounded-3xl border border-zinc-800 bg-zinc-900/70 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium text-zinc-300">
                {isMicActive ? (
                  <Mic className="h-4 w-4 text-emerald-400" />
                ) : (
                  <Pause className="h-4 w-4 text-zinc-500" />
                )}
                Live transcript
              </div>

              <div className="max-h-[420px] space-y-3 overflow-y-auto">
                {transcripts.length === 0 ? (
                  <div className="text-sm text-zinc-500">
                    No transcript yet. Connect the live agent and ask a question.
                  </div>
                ) : (
                  transcripts.map((item, idx) => (
                    <div
                      key={`${item.speaker}-${idx}`}
                      className={`rounded-2xl px-4 py-3 text-sm ${
                        item.speaker === "agent"
                          ? "bg-zinc-800 text-zinc-100"
                          : "bg-emerald-950/60 text-emerald-100"
                      }`}
                    >
                      <div className="mb-1 text-[11px] uppercase tracking-wide opacity-70">
                        {item.speaker}
                      </div>
                      <div>{item.text || (item.final ? "" : "...")}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}