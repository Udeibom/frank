"use client"
/**
 * RhythmIntake: tap or drum a rhythm on a desk, or say it ("boom, tss, boom boom, tss"), and have Frank
 * play it back on drums to check it heard you right. The rhythm only becomes part of the song's feel after
 * the person says "yes, that's it" (start-from-any-input spec 02, requirement 4).
 */
import { useEffect, useRef, useState } from "react"
import { Check, Drum, Loader2, Pause, Play, RotateCcw, Square } from "lucide-react"
import { useRecorder } from "@/hooks/useRecorder"
import { ApiError } from "@/lib/api/client"
import { rhythmToGroove, type RhythmIntakeResult } from "@/lib/api/intake"
import { Button } from "@/components/ui/button"
import type { MusicalFingerprint } from "@/types/project"

const MAX_SECONDS = 30

interface RhythmIntakeProps {
  projectId: string
  /** The person said "yes, that's my rhythm". Carries the speed and the pattern. */
  onConfirmed: (hints: Partial<MusicalFingerprint>) => void
  onSay: (message: string) => void
}

type Heard = Extract<RhythmIntakeResult, { ok: true }>

function explainFailure(err: unknown): string {
  const connection = !(err instanceof ApiError) || err.status >= 500
  return connection
    ? "I lost the connection for a moment, so I couldn't finish listening. Want to try tapping it again?"
    : "Something went wrong while I was listening. Want to try again?"
}

export function RhythmIntake({ projectId, onConfirmed, onSay }: RhythmIntakeProps) {
  const recorder = useRecorder()
  const pendingUpload = useRef(false)
  const [working, setWorking] = useState(false)
  const [heard, setHeard] = useState<Heard | null>(null)
  const [playing, setPlaying] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  function finishRecording() {
    pendingUpload.current = true
    recorder.stop()
  }

  useEffect(() => {
    if (recorder.status === "recording" && recorder.durationSeconds >= MAX_SECONDS) finishRecording()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recorder.durationSeconds, recorder.status])

  useEffect(() => {
    if (!pendingUpload.current || !recorder.audioBlob) return
    pendingUpload.current = false
    setWorking(true)
    rhythmToGroove(projectId, recorder.audioBlob, recorder.fileExtension)
      .then((result) => {
        if (result.ok) {
          setHeard(result)
          onSay("Here's the rhythm I heard. Have a listen. Is that it?")
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

  useEffect(() => {
    if (!heard) return
    const audio = new Audio(heard.preview_url)
    audioRef.current = audio
    audio.loop = true
    audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false))
    return () => {
      audio.pause()
      audioRef.current = null
    }
  }, [heard])

  function togglePlay() {
    const audio = audioRef.current
    if (!audio) return
    if (playing) {
      audio.pause()
      setPlaying(false)
    } else {
      audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false))
    }
  }

  function handleYes() {
    if (!heard) return
    const { groove } = heard
    setHeard(null)
    onConfirmed({
      tempo_bpm: groove.tempo_confidence >= 0.6 ? groove.tempo_bpm : undefined,
      groove: { kick: groove.kick, hat: groove.hat },
    } as Partial<MusicalFingerprint>)
  }

  function handleNotQuite() {
    setHeard(null)
    onSay("No problem. Tap it again whenever you're ready, nice and steady, a bar or two is plenty.")
  }

  if (working) {
    return (
      <div role="status" aria-live="polite" className="flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        <span>Listening to your rhythm… this usually takes a few seconds.</span>
      </div>
    )
  }
  if (heard) {
    return (
      <div role="group" aria-label="Check your rhythm" className="flex flex-col gap-2 rounded-md bg-primary/10 p-2">
        <p className="text-xs text-foreground/90">Is this your rhythm?</p>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={togglePlay} aria-label={playing ? "Pause your rhythm" : "Play your rhythm"}>
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
      <Button variant="ghost" size="sm" onClick={finishRecording} className="w-full justify-start text-destructive hover:text-destructive">
        <Square className="h-4 w-4 fill-current" aria-hidden="true" />
        Stop tapping ({recorder.durationSeconds}s)
      </Button>
    )
  }
  return (
    <div className="flex flex-col gap-1">
      <Button variant="ghost" size="sm" onClick={() => recorder.start()} className="w-full justify-start text-muted-foreground">
        <Drum className="h-4 w-4" aria-hidden="true" />
        Tap out a rhythm
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
