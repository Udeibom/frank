"use client"

/**
 * useRecorder — in-browser audio recording via MediaRecorder API.
 * The browser only captures audio; all processing happens on the backend.
 * Reused by the Idea Room (voice memos) and the Voice Room (vocal takes).
 */

import { useCallback, useRef, useState } from "react"

export type RecorderStatus = "idle" | "requesting" | "recording" | "stopped" | "denied"

interface UseRecorderResult {
  status: RecorderStatus
  durationSeconds: number
  inputLevel: number
  audioBlob: Blob | null
  audioUrl: string | null
  mimeType: string
  fileExtension: string
  start: () => Promise<void>
  stop: () => void
  reset: () => void
  error: string | null
}

function extensionForMime(mime: string): string {
  if (mime.includes("webm")) return "webm"
  if (mime.includes("mp4")) return "mp4"
  if (mime.includes("ogg")) return "ogg"
  return "webm"
}

export function useRecorder(): UseRecorderResult {
  const [status, setStatus] = useState<RecorderStatus>("idle")
  const [durationSeconds, setDurationSeconds] = useState(0)
  const [inputLevel, setInputLevel] = useState(0)
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const rafRef = useRef<number | null>(null)
  const recordedMimeRef = useRef<string>("audio/webm")
  const [mimeType, setMimeType] = useState("audio/webm")

  const cleanup = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    streamRef.current?.getTracks().forEach((t) => t.stop())
    if (audioCtxRef.current && audioCtxRef.current.state !== "closed") {
      audioCtxRef.current.close()
    }
    streamRef.current = null
    audioCtxRef.current = null
    analyserRef.current = null
  }, [])

  // Monitor input level for the recording meter (display only — no processing)
  const monitorLevel = useCallback(() => {
    const analyser = analyserRef.current
    if (!analyser) return
    const data = new Uint8Array(analyser.frequencyBinCount)
    analyser.getByteTimeDomainData(data)
    let peak = 0
    for (let i = 0; i < data.length; i++) {
      const v = Math.abs(data[i] - 128) / 128
      if (v > peak) peak = v
    }
    setInputLevel(peak)
    rafRef.current = requestAnimationFrame(monitorLevel)
  }, [])

  const start = useCallback(async () => {
    setError(null)
    setStatus("requesting")
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      // Set up level metering
      const audioCtx = new AudioContext()
      audioCtxRef.current = audioCtx
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 512
      source.connect(analyser)
      analyserRef.current = analyser

      // Set up the recorder — pick a mimeType the browser actually supports.
      // Safari doesn't support webm; it records mp4/aac instead.
      chunksRef.current = []
      const preferredTypes = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
        "audio/ogg",
      ]
      const mimeType =
        preferredTypes.find((t) => MediaRecorder.isTypeSupported(t)) || ""
      recordedMimeRef.current = mimeType || "audio/webm"
      setMimeType(recordedMimeRef.current)
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream)
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recordedMimeRef.current,
        })
        setAudioBlob(blob)
        setAudioUrl(URL.createObjectURL(blob))
      }
      mediaRecorderRef.current = recorder
      recorder.start()

      setStatus("recording")
      setDurationSeconds(0)
      timerRef.current = setInterval(() => {
        setDurationSeconds((d) => d + 1)
      }, 1000)

      monitorLevel()
    } catch (err) {
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setStatus("denied")
        setError("Frank needs permission to use your microphone.")
      } else {
        setStatus("idle")
        setError("Couldn't start recording. Check your microphone.")
      }
      cleanup()
    }
  }, [monitorLevel, cleanup])

  const stop = useCallback(() => {
    mediaRecorderRef.current?.stop()
    setStatus("stopped")
    setInputLevel(0)
    cleanup()
  }, [cleanup])

  const reset = useCallback(() => {
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setStatus("idle")
    setDurationSeconds(0)
    setInputLevel(0)
    setAudioBlob(null)
    setAudioUrl(null)
    setError(null)
    chunksRef.current = []
  }, [audioUrl])

  return {
    status,
    durationSeconds,
    inputLevel,
    audioBlob,
    audioUrl,
    mimeType,
    fileExtension: extensionForMime(mimeType),
    start,
    stop,
    reset,
    error,
  }
}
