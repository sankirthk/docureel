export class PCMPlayer {
  private audioContext: AudioContext | null = null;
  private nextTime = 0;
  private activeSources = new Set<AudioBufferSourceNode>();
  private readonly sampleRate: number;

  constructor(sampleRate = 24000) {
    this.sampleRate = sampleRate;
  }

  async init() {
    if (!this.audioContext) {
      this.audioContext = new AudioContext({
        sampleRate: this.sampleRate,
      });
    }

    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }

    if (this.nextTime === 0) {
      this.nextTime = this.audioContext.currentTime;
    }
  }

  private base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binary = window.atob(base64);
    const len = binary.length;
    const bytes = new Uint8Array(len);

    for (let i = 0; i < len; i++) {
      bytes[i] = binary.charCodeAt(i);
    }

    return bytes.buffer;
  }

  private pcm16ToFloat32(buffer: ArrayBuffer): Float32Array {
    const pcm = new Int16Array(buffer);
    const out = new Float32Array(pcm.length);

    for (let i = 0; i < pcm.length; i++) {
      out[i] = pcm[i] / 32768;
    }

    return out;
  }

  async playChunk(base64Data: string) {
    await this.init();
    if (!this.audioContext) return;

    const pcmBuffer = this.base64ToArrayBuffer(base64Data);
    const samples = this.pcm16ToFloat32(pcmBuffer);

    const audioBuffer = this.audioContext.createBuffer(
      1,
      samples.length,
      this.sampleRate
    );
    audioBuffer.getChannelData(0).set(samples);

    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);

    const startAt = Math.max(this.audioContext.currentTime, this.nextTime);
    source.start(startAt);
    this.nextTime = startAt + audioBuffer.duration;

    this.activeSources.add(source);
    source.onended = () => {
      this.activeSources.delete(source);
    };
  }

  /** How many milliseconds of audio are still scheduled to play. */
  remainingMs(): number {
    if (!this.audioContext) return 0;
    const remaining = this.nextTime - this.audioContext.currentTime;
    return Math.max(0, remaining) * 1000;
  }

  stop() {
    for (const source of this.activeSources) {
      try {
        source.stop();
      } catch {
        // ignore
      }
    }
    this.activeSources.clear();

    if (this.audioContext) {
      this.nextTime = this.audioContext.currentTime;
    }
  }

  async close() {
    this.stop();
    if (this.audioContext) {
      await this.audioContext.close();
      this.audioContext = null;
      this.nextTime = 0;
    }
  }
}