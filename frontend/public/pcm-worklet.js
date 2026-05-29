// AudioWorklet: mic → 16 kHz 16-bit mono PCM → main thread → WebSocket → AWS.
//
// Batch to ~100 ms frames before posting. process() fires per audio quantum
// (every 128 samples), far too often to send each as its own WebSocket frame.
// Batching keeps real-time pacing (100 ms of audio = 100 ms wall clock), which
// AWS Transcribe needs to endpoint and emit finals — sending faster than real
// time makes it only ever return partials.

const TARGET_RATE = 16000
const FLUSH_SAMPLES = TARGET_RATE / 10  // ~100 ms of 16 kHz audio

class PCMWorklet extends AudioWorkletProcessor {
  constructor() {
    super()
    this._step = sampleRate / TARGET_RATE
    this._cursor = 0
    this._buf = []
  }

  // Linear-interpolation downsample from sampleRate (e.g. 48000) to TARGET_RATE.
  _resample(input) {
    const out = []
    while (this._cursor < input.length) {
      const idx = Math.floor(this._cursor)
      const frac = this._cursor - idx
      const a = input[idx]
      const b = idx + 1 < input.length ? input[idx + 1] : a
      out.push(a + (b - a) * frac)
      this._cursor += this._step
    }
    this._cursor -= input.length
    return out
  }

  _flush() {
    const samples = this._buf
    this._buf = []
    const buf = new ArrayBuffer(samples.length * 2)
    const view = new DataView(buf)
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]))
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    }
    this.port.postMessage(buf, [buf])
  }

  process(inputs) {
    const channel = inputs[0]?.[0]
    if (!channel || channel.length === 0) return true

    const resampled = this._resample(channel)
    for (let i = 0; i < resampled.length; i++) this._buf.push(resampled[i])

    if (this._buf.length >= FLUSH_SAMPLES) this._flush()
    return true
  }
}

registerProcessor('pcm-worklet', PCMWorklet)
