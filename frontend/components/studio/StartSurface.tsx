"use client"

/**
 * StartSurface — one way in (start-from-any-input spec 02, requirement 1). Type how it should feel or paste your
 * words; hum, sing or say it into the mic; or tap a rhythm. Nobody chooses a path first: Frank works out what it
 * got (several lines are words, a short passage is a description; a recording is a tune or a description).
 */

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { RhythmIntake } from "@/components/studio/RhythmIntake"
import { useRecorder } from "@/hooks/useRecorder"
import { saveLyrics } from "@/lib/api/lyrics"
import { getFingerprint, saveFingerprint } from "@/lib/api/feel"
import {
  confirmTune,
  describeSong,
  readWords,
  rejectTune,
  startFromRecording,
  type HumIntakeResult,
} from "@/lib/api/intake"
import { pollJob } from "@/lib/api/jobs"
import { useProjectStore } from "@/store/project"
import { useAudio } from "@/store/audio"
import type { MusicalFingerprint } from "@/types/project"
import { Mic, Square, Loader2, Play, Send } from "lucide-react"
import { cn } from "@/lib/utils"

type Heard = Extract<HumIntakeResult, { ok: true }>

interface StartSurfaceProps {
  projectId: string
  /** Where Frank's words go; defaults to a small list inside the surface. */
  onSay?: (message: string) => void
}

export function StartSurface({ projectId, onSay }: StartSurfaceProps) {
  const recorder = useRecorder()
  const storeRefresh = useProjectStore((st) => st.refresh)
  const refresh = () => {
    storeRefresh(projectId).catch(() => {})   // every room re-reads the song
  }
  const [text, setText] = useState("")
  const [working, setWorking] = useState<string | null>(null)
  const [said, setSaid] = useState<string[]>([])
  const [heard, setHeard] = useState<Heard | null>(null)
  const pendingRef = useRef(false)

  const say = (m: string) => (onSay ? onSay(m) : setSaid((xs) => [...xs.slice(-3), m]))

  async function fillGaps(hints: Partial<MusicalFingerprint>) {
    // Hints only fill what is not settled yet (requirement 6.4).
    const current = (await getFingerprint(projectId).catch(() => null))?.fingerprint ?? {}
    const merged = { ...current } as Record<string, unknown>
    for (const [k, v] of Object.entries(hints)) {
      if (merged[k] === undefined || merged[k] === null || merged[k] === "") merged[k] = v
    }
    await saveFingerprint(projectId, merged as unknown as MusicalFingerprint)
    refresh()
  }

  async function sendText() {
    const value = text.trim()
    if (!value) return
    setWorking("Reading what you wrote…")
    try {
      const lines = value.split("\n").filter((l) => l.trim()).length
      if (lines >= 3) {
        await saveLyrics(projectId, value)
        const r = await readWords(projectId, value)
        say(r.message)
      } else {
        const r = await describeSong(projectId, value)
        say(r.message)
      }
      setText("")
      refresh()
    } catch (err) {
      say(err instanceof Error && err.message ? err.message : "I couldn't take that in just now. Want to try again?")
    } finally {
      setWorking(null)
    }
  }

  // A finished recording goes to the backend, which decides: a tune or a description.
  useEffect(() => {
    if (!pendingRef.current || !recorder.audioBlob) return
    pendingRef.current = false
    const blob = recorder.audioBlob
    const ext = recorder.fileExtension
    recorder.reset()
    setWorking("Listening…")
    startFromRecording(projectId, blob, ext)
      .then(async (r) => {
        if (r.kind === "description" && r.description) {
          say(r.description.heard ? `I heard: \u201c${r.description.heard}\u201d. ${r.description.message}` : r.description.message)
          refresh()
          return
        }
        if (r.job_id) {
          setWorking("Finding the tune in that… about half a minute.")
          const done = await pollJob(r.job_id)
          const res = done.result as unknown as HumIntakeResult
          if (res.ok) {
            setHeard(res)
            say(res.description)
          } else {
            say(res.reason)
          }
        }
      })
      .catch((err) => say(err instanceof Error && err.message ? err.message : "That didn't come through. Want to try again?"))
      .finally(() => setWorking(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recorder.audioBlob])

  async function yes() {
    if (!heard) return
    const r = await confirmTune(projectId, heard.version_id)
    setHeard(null)
    await fillGaps(r.fingerprint_hints)
    say(r.question ?? "That's the song's tune now. The music will be built around it.")
  }

  async function notQuite() {
    if (!heard) return
    await rejectTune(projectId, heard.version_id).catch(() => {})
    setHeard(null)
    say("No problem. Hum it again whenever you like.")
  }

  const isRecording = recorder.status === "recording"

  return (
    <section aria-label="Start your song from anything" className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <label htmlFor="start-text" className="text-xs text-muted-foreground">
          Type how it should feel, or paste your words
        </label>
        <textarea
          id="start-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          placeholder="It should feel like walking home alone after a party…"
          className="w-full resize-y rounded-lg border border-border bg-background px-3 py-2 text-sm"
        />
        <Button size="sm" className="self-end" onClick={sendText} disabled={!text.trim() || Boolean(working)}>
          <Send className="h-3.5 w-3.5" /> Start from this
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => {
            if (isRecording) {
              pendingRef.current = true
              recorder.stop()
            } else {
              recorder.start()
            }
          }}
          disabled={Boolean(working) && !isRecording}
          className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-full transition-all",
            isRecording ? "bg-red-500 text-white" : "bg-primary text-primary-foreground hover:scale-105",
          )}
          aria-label={isRecording ? "Stop recording" : "Hum it, sing it or say it"}
        >
          {isRecording ? <Square className="h-5 w-5 fill-current" /> : <Mic className="h-5 w-5" />}
        </button>
        <p className="text-sm text-muted-foreground">
          {isRecording ? `Recording… ${recorder.durationSeconds}s` : "Hum it, sing it, or just say how it should feel"}
        </p>
      </div>

      {heard && (
        <div className="rounded-xl border border-primary/30 bg-card p-3">
          <p className="mb-2 text-sm text-foreground">Is this your tune?</p>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => {
              void useAudio.getState().play({ id: `start-hum:${heard.preview_url}`, url: heard.preview_url, label: "Your tune, as I heard it", material: "feel" }, { at: 0 })
            }}>
              <Play className="h-3.5 w-3.5" /> Hear it
            </Button>
            <Button size="sm" onClick={yes}>Yes, that&apos;s it</Button>
            <Button size="sm" variant="outline" onClick={notQuite}>Not quite</Button>
          </div>
        </div>
      )}

      <RhythmIntake projectId={projectId} onConfirmed={(hints) => fillGaps(hints).then(() => say("Got your rhythm. The drums will follow it."))} onSay={say} />

      {working && (
        <p className="flex items-center gap-2 text-xs text-muted-foreground" role="status">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> {working}
        </p>
      )}
      {!onSay && said.length > 0 && (
        <div className="flex flex-col gap-2" aria-live="polite">
          {said.map((m, i) => (
            <p key={i} className="rounded-lg bg-secondary/60 px-3 py-2 text-sm text-foreground">{m}</p>
          ))}
        </div>
      )}
    </section>
  )
}
