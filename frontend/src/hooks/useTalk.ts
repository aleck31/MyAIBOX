/**
 * Realtime voice (Talk with Agent) bridge — full-duplex.
 *
 * Capture path reuses the transcribe pattern: getUserMedia → AudioContext →
 * AudioWorklet (`/pcm-worklet.js`) → 16 kHz PCM → WebSocket /api/talk/stream.
 * Playback path (new): the server streams base64 PCM audio frames back; we
 * decode and schedule them gaplessly. Barge-in: an {interrupted} frame stops
 * and flushes any queued playback so the user can cut in.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

interface TalkFrame {
  type: 'transcript' | 'audio' | 'interrupted' | 'error'
  text?: string
  role?: 'user' | 'assistant'
  final?: boolean
  audio?: string        // base64 PCM
  sample_rate?: number
  message?: string
}

interface UseTalkOptions {
  /** A transcript segment (user or assistant), partial or final. */
  onTranscript?: (text: string, role: 'user' | 'assistant', final: boolean) => void
  /** Connection / model errors. */
  onError?: (message: string) => void
  /** Connection opened / closed — drives the call UI state. */
  onOpen?: () => void
  onClose?: () => void
}

export interface TalkHandle {
  /** True from connect() until the WS handshake + session are up. */
  connecting: boolean
  connected: boolean
  /** True while the model is speaking (audio is queued/playing). */
  speaking: boolean
  connect: (voiceId?: string, history?: Array<{ role: string; text: string }>) => Promise<void>
  hangup: () => void
}

function b64ToInt16(b64: string): Int16Array {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new Int16Array(bytes.buffer)
}

export function useTalk(agentId: string, options: UseTalkOptions = {}): TalkHandle {
  const [connecting, setConnecting] = useState(false)
  const [connected, setConnected] = useState(false)
  const [speaking, setSpeaking] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const inCtxRef = useRef<AudioContext | null>(null)     // capture (16 kHz)
  const outCtxRef = useRef<AudioContext | null>(null)    // playback
  const streamRef = useRef<MediaStream | null>(null)
  const nextPlayRef = useRef(0)                          // scheduled playback cursor
  const sourcesRef = useRef<AudioBufferSourceNode[]>([]) // active playback sources (for barge-in flush)

  const cbRef = useRef(options)
  cbRef.current = options

  const flushPlayback = useCallback(() => {
    for (const src of sourcesRef.current) {
      try { src.stop() } catch { /* ignore */ }
    }
    sourcesRef.current = []
    nextPlayRef.current = 0
    setSpeaking(false)
  }, [])

  const playAudio = useCallback((b64: string, sampleRate: number) => {
    const ctx = outCtxRef.current
    if (!ctx) return
    const pcm = b64ToInt16(b64)
    const buf = ctx.createBuffer(1, pcm.length, sampleRate)
    const ch = buf.getChannelData(0)
    for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 32768
    const src = ctx.createBufferSource()
    src.buffer = buf
    src.connect(ctx.destination)
    const now = ctx.currentTime
    const at = Math.max(now, nextPlayRef.current)
    src.start(at)
    nextPlayRef.current = at + buf.duration
    sourcesRef.current.push(src)
    setSpeaking(true)
    src.onended = () => {
      sourcesRef.current = sourcesRef.current.filter(s => s !== src)
      if (sourcesRef.current.length === 0) setSpeaking(false)
    }
  }, [])

  const teardown = useCallback(() => {
    flushPlayback()
    try { wsRef.current?.close() } catch { /* ignore */ }
    wsRef.current = null
    if (inCtxRef.current) { inCtxRef.current.close().catch(() => {}); inCtxRef.current = null }
    if (outCtxRef.current) { outCtxRef.current.close().catch(() => {}); outCtxRef.current = null }
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    setConnecting(false)
    setConnected(false)
    setSpeaking(false)
  }, [flushPlayback])

  const connect = useCallback(async (voiceId?: string, history?: Array<{ role: string; text: string }>) => {
    if (wsRef.current) return
    setConnecting(true)
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      })
    } catch {
      cbRef.current.onError?.('microphone permission denied')
      setConnecting(false)
      return
    }
    streamRef.current = stream

    const inCtx = new AudioContext()
    inCtxRef.current = inCtx
    outCtxRef.current = new AudioContext()
    try {
      await inCtx.audioWorklet.addModule(`/pcm-worklet.js?v=${__APP_VERSION__}`)
    } catch (e) {
      cbRef.current.onError?.(`audio worklet load failed: ${(e as Error).message}`)
      teardown()
      return
    }

    const q = voiceId ? `?voice_id=${encodeURIComponent(voiceId)}` : ''
    const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/talk/stream/${encodeURIComponent(agentId)}${q}`
    const ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    const source = inCtx.createMediaStreamSource(stream)
    const node = new AudioWorkletNode(inCtx, 'pcm-worklet')
    // Gate audio until the `start` frame is sent — the backend reads the first
    // frame as setup (prior transcript), so audio must not race ahead of it.
    let started = false
    node.port.onmessage = (ev) => {
      if (started && ws.readyState === WebSocket.OPEN) ws.send(ev.data as ArrayBuffer)
    }
    source.connect(node)
    const muted = inCtx.createGain()
    muted.gain.value = 0
    node.connect(muted)
    muted.connect(inCtx.destination)

    ws.onopen = () => {
      // First frame = setup: the front-end transcript the user hasn't cleared,
      // so a session evicted by TTL still resumes (cache hit ignores it).
      ws.send(JSON.stringify({ type: 'start', history: history || [] }))
      started = true
      setConnecting(false); setConnected(true); cbRef.current.onOpen?.()
    }
    ws.onmessage = (ev) => {
      let frame: TalkFrame
      try { frame = JSON.parse(ev.data as string) } catch { return }
      switch (frame.type) {
        case 'transcript':
          if (frame.text) cbRef.current.onTranscript?.(frame.text, frame.role || 'assistant', !!frame.final)
          break
        case 'audio':
          if (frame.audio) playAudio(frame.audio, frame.sample_rate || 16000)
          break
        case 'interrupted':
          flushPlayback()   // barge-in: drop queued model speech
          break
        case 'error':
          cbRef.current.onError?.(frame.message || 'voice error')
          break
      }
    }
    ws.onerror = () => cbRef.current.onError?.('connection error')
    ws.onclose = () => { if (wsRef.current === ws) { teardown(); cbRef.current.onClose?.() } }
  }, [agentId, teardown, playAudio, flushPlayback])

  const hangup = useCallback(() => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      try { ws.send('__end__') } catch { /* ignore */ }
    }
    teardown()
  }, [teardown])

  useEffect(() => () => teardown(), [teardown])

  return { connecting, connected, speaking, connect, hangup }
}
