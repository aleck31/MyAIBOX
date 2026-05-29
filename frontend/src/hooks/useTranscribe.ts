/**
 * Microphone → AWS Transcribe streaming bridge.
 *
 * - getUserMedia → AudioContext → AudioWorklet (`/pcm-worklet.js`)
 *   produces raw 16 kHz 16-bit PCM chunks.
 * - WebSocket to /api/asking/transcribe forwards those chunks to AWS
 *   Transcribe streaming and pushes back partial / final transcripts.
 *
 * Lifecycle (the subtle part):
 *   start()  → open WS + mic, stream audio
 *   stop()   → stop the mic, send "__end__", but KEEP the WebSocket open.
 *              The server flushes AWS Transcribe (end_stream), waits for the
 *              trailing `final`, sends it, then closes the socket. Only on
 *              that close (or a safety timeout) do we tear down. Closing the
 *              socket eagerly in stop() is exactly what dropped the final
 *              before — AWS cancels the in-flight response when the transport
 *              goes away.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

interface TranscriptMessage {
  type: 'partial' | 'final' | 'error'
  text?: string
  message?: string
  lang?: string
}

interface UseTranscribeOptions {
  /** Live, not-yet-finalized transcript. Replaces the previous partial. */
  onPartial?: (text: string) => void
  /** A finalized segment (sentence break, or the flush triggered by stop()). */
  onFinal?: (text: string) => void
  /** Transport / Transcribe errors. */
  onError?: (message: string) => void
}

export interface TranscribeHandle {
  /** True while the mic is streaming audio. */
  isRecording: boolean
  /** True after stop() until the trailing final arrives and the socket closes. */
  isFinalizing: boolean
  start: () => Promise<void>
  stop: () => void
}

// Safety net only: the server normally delivers the trailing final in ~100 ms
// and then closes the socket (onclose → teardown). This timeout must stay
// LONGER than the server's own finalize timeout, otherwise the client closes
// first and cancels AWS's in-flight final — which is exactly the bug that made
// stop() hang for seconds. Server waits 3 s; we give it 10 s of slack.
const FINALIZE_TIMEOUT_MS = 10000

export function useTranscribe(options: UseTranscribeOptions = {}): TranscribeHandle {
  const [isRecording, setIsRecording] = useState(false)
  const [isFinalizing, setIsFinalizing] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const finalizeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const onPartialRef = useRef(options.onPartial)
  const onFinalRef = useRef(options.onFinal)
  const onErrorRef = useRef(options.onError)
  onPartialRef.current = options.onPartial
  onFinalRef.current = options.onFinal
  onErrorRef.current = options.onError

  // Fully release the socket + audio graph. Idempotent.
  const teardown = useCallback(() => {
    if (finalizeTimerRef.current) {
      clearTimeout(finalizeTimerRef.current)
      finalizeTimerRef.current = null
    }
    try { wsRef.current?.close() } catch { /* ignore */ }
    wsRef.current = null
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => { /* ignore */ })
      audioCtxRef.current = null
    }
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    setIsRecording(false)
    setIsFinalizing(false)
  }, [])

  // Stop only the microphone + audio graph, leaving the WebSocket open so the
  // server can still deliver the trailing final.
  const stopAudioOnly = useCallback(() => {
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => { /* ignore */ })
      audioCtxRef.current = null
    }
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
  }, [])

  const start = useCallback(async () => {
    if (wsRef.current) return  // already running
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
      })
    } catch {
      onErrorRef.current?.('microphone permission denied')
      return
    }
    streamRef.current = stream

    const audioCtx = new AudioContext()
    audioCtxRef.current = audioCtx
    try {
      // /pcm-worklet.js lives in public/ so its URL is unhashed and the browser
      // caches it aggressively — a stale copy silently breaks audio pacing.
      // Pin it to the app version so each release fetches the right worklet.
      await audioCtx.audioWorklet.addModule(`/pcm-worklet.js?v=${__APP_VERSION__}`)
    } catch (e) {
      onErrorRef.current?.(`audio worklet load failed: ${(e as Error).message}`)
      teardown()
      return
    }

    const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/asking/transcribe`
    const ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    const source = audioCtx.createMediaStreamSource(stream)
    const node = new AudioWorkletNode(audioCtx, 'pcm-worklet')
    node.port.onmessage = (ev) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(ev.data as ArrayBuffer)
    }
    source.connect(node)
    // Chromium only runs the worklet if the graph terminates at a destination;
    // route through a 0-gain node so nothing echoes to the speakers.
    const muted = audioCtx.createGain()
    muted.gain.value = 0
    node.connect(muted)
    muted.connect(audioCtx.destination)

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as TranscriptMessage
        if (msg.type === 'error') {
          onErrorRef.current?.(msg.message || 'transcribe error')
        } else if (msg.type === 'partial' && msg.text) {
          onPartialRef.current?.(msg.text)
        } else if (msg.type === 'final' && msg.text) {
          onFinalRef.current?.(msg.text)
        }
      } catch {
        // Server only sends JSON text frames; ignore malformed ones.
      }
    }
    ws.onerror = () => onErrorRef.current?.('connection error')
    ws.onclose = () => {
      if (wsRef.current === ws) teardown()
    }

    setIsRecording(true)
    setIsFinalizing(false)
  }, [teardown])

  const stop = useCallback(() => {
    const ws = wsRef.current
    // Stop capturing immediately so no more audio is sent...
    stopAudioOnly()
    setIsRecording(false)

    if (ws && ws.readyState === WebSocket.OPEN) {
      // ...but keep the socket open: tell the server to flush, then wait for
      // the trailing final + server-initiated close (onclose → teardown).
      try { ws.send('__end__') } catch { /* ignore */ }
      setIsFinalizing(true)
      finalizeTimerRef.current = setTimeout(() => {
        // Server didn't close in time — give up and release everything.
        teardown()
      }, FINALIZE_TIMEOUT_MS)
    } else {
      teardown()
    }
  }, [stopAudioOnly, teardown])

  // Defensive cleanup if the component unmounts mid-recording.
  useEffect(() => () => teardown(), [teardown])

  return { isRecording, isFinalizing, start, stop }
}
