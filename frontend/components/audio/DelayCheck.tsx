"use client"

/**
 * DelayCheck — a one-time timing check (sing-it spec 06, requirement 3.1). Every computer adds a small delay
 * between what you hear and what the mic records. Frank plays four clicks; you clap along; Frank measures the gap
 * and lines up every take you record on this computer from then on.
 */

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { useRecorder } from "@/hooks/useRecorder"
import { SessionPlayer } from "@/lib/audio/sessionPlayer"
import { sendDelayCheck } from "@/lib/api/voice"
import { Loader2, Timer, X } from "lucide-react"
import { useAudio } from "@/store/audio"

const CLICKS = 4
const EVERY = 0.75

interface DelayCheckProps {
  projectId: string
  onDone: (message: string) => void
  onClose: () => void
}

export function DelayCheck({ projectId, onDone, onClose }: DelayCheckProps) {
  const recorder = useRecorder()
  const [phase, setPhase] = useState<"idle" | "listening" | "sending">("idle")
  const [note, setNote] = useState<string | null>(null)
  const playerRef = useRef<SessionPlayer | null>(null)

  const clicksRef = useRef<number[] | null>(null)

  async function run() {
    // The clicks must be the only sound, or the measurement is wrong.
    useAudio.getState().pause()
    setNote(null)
    setPhase("listening")
    playerRef.current ??= new SessionPlayer()
    await recorder.start()
    const startedAt = recorder.getStartedAt() ?? performance.now()
    const clickTimes = await playerRef.current.clicks(CLICKS, EVERY, 0.8)
    clicksRef.current = clickTimes.map((t) => (t - startedAt) / 1000)
    setTimeout(() => recorder.stop(), (0.8 + CLICKS * EVERY + 0.6) * 1000)
  }

  // When the short recording is ready, send it with the click times.
  useEffect(() => {
    const blob = recorder.audioBlob
    const clicks = clicksRef.current
    if (!blob || !clicks) return
    clicksRef.current = null
    setPhase("sending")
    sendDelayCheck(projectId, blob, recorder.fileExtension, clicks)
      .then((res) => (res.ok ? onDone(res.message) : setNote(res.message)))
      .catch(() => setNote("That didn't go through. Want to try once more?"))
      .finally(() => {
        recorder.reset()
        setPhase("idle")
      })
  }, [recorder.audioBlob, recorder.fileExtension, recorder, projectId, onDone])

  return (
    <section aria-label="Line up my recordings" className="rounded-md border border-line bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <p className="flex items-center gap-2 text-base font-medium text-ink">
          <Timer className="h-4 w-4 text-ink-2" aria-hidden="true" /> Line up my recordings (once)
        </p>
        <button onClick={onClose} aria-label="Not now" className="rounded-sm p-1 text-ink-3 hover:text-ink">
          <X className="h-4 w-4" />
        </button>
      </div>
      <p className="mb-3 text-sm text-ink-2">
        Every computer adds a tiny delay to recordings. I&apos;ll play four clicks: clap along, right on each one. Then
        every take you sing lands exactly on the beat.
      </p>
      <Button size="sm" variant="outline" onClick={run} disabled={phase !== "idle"}>
        {phase !== "idle" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
        {phase === "listening" ? "Clap on each click…" : phase === "sending" ? "Measuring…" : "Start the check"}
      </Button>
      {note && <p className="mt-2 text-sm text-caution" role="status">{note}</p>}
    </section>
  )
}
