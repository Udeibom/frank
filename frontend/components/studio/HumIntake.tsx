"use client"

/**
 * HumIntake — hum a tune and have Frank play it back to check it heard you right.
 *
 * Records in the browser and sends the recording away; the browser does no audio
 * processing. Frank's version only becomes the song's tune after the person says
 * "yes, that's it" (start-from-any-input spec 02, requirements 3.4 and 3.5).
 *
 * What Frank says when something goes wrong is honest about the cause: a dropped
 * connection is never presented as a problem with the hum.
 */

import { useEffect, useRef, useState } from "react"
import { Check, Loader2, Music, Pause, Play, RotateCcw, Square } from "lucide-react"
import { useRecorder } from "@/hooks/useRecorder"
import { ApiError } from "@/lib/api/client"
import { confirmTune, humToTune, rejectTune, type HumIntakeResult } from "@/lib/api/intake"
import { Button } from "@/components/ui/button"
import { useAudio, usePlayback, type Track } from "@/store/audio"
import type { MusicalFingerprint } from "@/types/project"

/** A minute is far more than a tune needs; recording stops by itself here. */
const MAX_HUM_SECONDS = 60

interface HumIntakeProps {
  projectId: string
  /** The person said "yes, that's my tune". Hints carry only what Frank is confident about. */
  onConfirmed: (info: {
    hints: Partial<MusicalFingerprint>
    description: string
    /** What Frank could not pin down, most important first: "mood" and/or "speed". */
    unsureAbout: string[]
  }) => void
  /** Anything Frank wants to say in the conversation (kind reasons, next steps). */
  onSay: (message: string) => void
  /** "stage": a real control on the room's stage. "chat": the compact link above the conversation input. */
  appearance?: "chat" | "stage"
}

type Heard = Extract<HumIntakeResult, { ok: true }>

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

/** The honest reason a hum did not work out, in Frank's own voice. */
function explainFailure(err: unknown): string {
  // The connection dropping says nothing about the hum.
  const connection = !(err instanceof ApiError) || err.status >= 500
  if (connection) {
    return "I lost the connection for a moment, so I couldn't finish listening. Your hum is safe. Want to try again?"
  }
  return "Something went wrong while I was listening. Want to try again?"
}

export function HumIntake({ projectId, onConfirmed, onSay, appearance = "chat" }: HumIntakeProps) {
  const recorder = useRecorder()
  const pendingUpload = useRef(false)
  const [working, setWorking] = useState(false)
  const [heard, setHeard] = useState<Heard | null>(null)
  // Frank's version of the tune plays through the shared engine (one sound at a time).
  const tuneTrack: Track | null = heard ? { id: `hum:${heard.version_id}`, url: heard.preview_url, label: "Your tune, as I heard it", material: "feel" } : null
  const { playing } = usePlayback(tuneTrack?.id)

  // Keyboard users must not lose their place when the button they pressed disappears.
  const startRef = useRef<HTMLButtonElement | null>(null)
  const stopRef = useRef<HTMLButtonElement | null>(null)
  const checkRef = useRef<HTMLDivElement | null>(null)

  function finishRecording() {
    pendingUpload.current = true
    recorder.stop()
  }

  // Stop by itself at the limit.
  useEffect(() => {
    if (recorder.status === "recording" && recorder.durationSeconds >= MAX_HUM_SECONDS) {
      finishRecording()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recorder.durationSeconds, recorder.status])

  // Send the recording once it has finished being captured.
  useEffect(() => {
    if (!pendingUpload.current || !recorder.audioBlob) return
    pendingUpload.current = false
    const blob = recorder.audioBlob
    const ext = recorder.fileExtension
    setWorking(true)
    humToTune(projectId, blob, ext)
      .then((result) => {
        if (result.ok) {
          setHeard(result)
          onSay(`${result.description} Have a listen. Is that your tune?`)
        } else {
          onSay(result.reason)
        }
      })
      .catch((err: unknown) => onSay(explainFailure(err)))
      .finally(() => {
        setWorking(false)
        recorder.reset()
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recorder.audioBlob])

  // Play Frank's version of the tune as soon as it arrives.
  useEffect(() => {
    if (tuneTrack) void useAudio.getState().play(tuneTrack)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [heard])

  // Move focus to whatever is now in front of the person.
  useEffect(() => {
    if (recorder.status === "recording") stopRef.current?.focus()
  }, [recorder.status])
  // (Only after something changed: never on first load, or the page would pull focus away from where the
  // person is about to type.)
  const before = useRef({ heard: false, working: false })
  useEffect(() => {
    const changed = before.current.heard !== Boolean(heard) || before.current.working !== working
    before.current = { heard: Boolean(heard), working }
    if (!changed) return
    if (heard) checkRef.current?.focus()
    else if (!working && recorder.status === "idle") startRef.current?.focus({ preventScroll: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [heard, working])

  function togglePlay() {
    if (tuneTrack) void useAudio.getState().toggle(tuneTrack, { at: playing ? undefined : 0 })
  }

  async function handleYes() {
    if (!heard) return
    const current = heard
    setWorking(true)
    try {
      const { fingerprint_hints, question } = await confirmTune(projectId, current.version_id)
      setHeard(null)
      onConfirmed({
        hints: fingerprint_hints,
        description: current.description,
        unsureAbout: current.unsure_about,
      })
      // A tune that disagrees with what the song already settled: Frank asks which should lead (spec 02, req 6.5).
      if (question) onSay(question)
    } catch {
      onSay("I couldn't save your tune just now. Want to say yes again?")
    } finally {
      setWorking(false)
    }
  }

  async function handleNotQuite() {
    if (!heard) return
    const current = heard
    setHeard(null)
    try {
      await rejectTune(projectId, current.version_id)
    } catch {
      /* remembering the "no" is best-effort; the person can simply hum again */
    }
    onSay("No problem. Hum it again whenever you're ready, and I'll listen more closely.")
  }

  if (working) {
    return (
      <div role="status" aria-live="polite" className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        <span>Listening closely to your hum… this usually takes a few seconds.</span>
      </div>
    )
  }

  if (heard) {
    return (
      <div
        ref={checkRef}
        tabIndex={-1}
        role="group"
        aria-label="Check your tune"
        className="flex flex-col gap-2 rounded-md bg-primary/10 p-2 outline-none"
      >
        <p className="text-xs text-foreground/90">Is this your tune?</p>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={togglePlay}
            aria-label={playing ? "Pause your tune" : "Play your tune"}
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {playing ? "Pause" : "Hear it again"}
          </Button>
          <Button size="sm" onClick={handleYes}>
            <Check className="h-4 w-4" />
            Yes, that&apos;s it
          </Button>
          <Button variant="ghost" size="sm" onClick={handleNotQuite}>
            <RotateCcw className="h-4 w-4" />
            Not quite
          </Button>
        </div>
      </div>
    )
  }

  if (recorder.status === "recording") {
    return (
      <Button
        ref={stopRef}
        variant="ghost"
        size="sm"
        onClick={finishRecording}
        className="w-full justify-start text-destructive hover:text-destructive"
      >
        <Square className="h-4 w-4 fill-current" aria-hidden="true" />
        Stop humming ({formatTime(recorder.durationSeconds)})
      </Button>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      <Button
        ref={startRef}
        variant={appearance === "stage" ? "outline" : "ghost"}
        size="sm"
        onClick={() => recorder.start()}
        className={
          appearance === "stage"
            ? "h-10 border-line bg-raised px-4 text-base text-ink hover:border-ink-3 hover:bg-raised"
            : "w-full justify-start text-muted-foreground"
        }
      >
        <Music className="h-4 w-4" aria-hidden="true" />
        Hum your tune
      </Button>
      {recorder.error && (
        <p role="alert" className="px-3 text-xs text-muted-foreground">
          {recorder.status === "denied"
            ? "I need your permission to use the microphone. You can allow it in your browser's address bar, then try again."
            : "I couldn't start the microphone. Is it plugged in and switched on?"}
        </p>
      )}
    </div>
  )
}
