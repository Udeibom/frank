"use client"

/**
 * VocalRecorder — the centerpiece of the Voice Room (sing-it spec 06).
 * A large record button with a live level meter and timer. The person picks where to start; Frank counts them in
 * (one bar of the beat, or four clicks at the very top), plays the beat and, if they like, the tune softly on a
 * voice-like sound to sing along with. They can practise a part on repeat without recording. The guide only plays
 * in their ears; the take is lined up with the beat on the server. Headphones are suggested, never required.
 */

import { useEffect, useRef, useState } from "react"
import { useRecorder } from "@/hooks/useRecorder"
import { Button } from "@/components/ui/button"
import { SessionPlayer } from "@/lib/audio/sessionPlayer"
import type { TakePlacement } from "@/lib/api/voice"
import { Mic, Square, Loader2, Headphones, Repeat, Music2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { useAudio } from "@/store/audio"

export interface SongSection {
  index: number
  label: string
  start: number
  end: number
}

interface VocalRecorderProps {
  beatUrl: string | null
  beatVersionId: string | null
  sections: SongSection[]
  secondsPerBeat: number
  guideUrl: string | null
  guideNote: string | null
  onWantGuide: () => Promise<void>
  uploading: boolean
  onRecorded: (blob: Blob, fileExtension: string, placement: TakePlacement | null, headphones: boolean | null) => void
  /** From the headphone check, when it was done. */
  initialHeadphones?: boolean
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

export function VocalRecorder({
  beatUrl,
  beatVersionId,
  sections,
  secondsPerBeat,
  guideUrl,
  guideNote,
  onWantGuide,
  uploading,
  onRecorded,
  initialHeadphones,
}: VocalRecorderProps) {
  const recorder = useRecorder()
  const [withBeat, setWithBeat] = useState(true)
  const [headphones, setHeadphones] = useState(Boolean(initialHeadphones))
  useEffect(() => {
    if (initialHeadphones) setHeadphones(true)
  }, [initialHeadphones])
  const [startAt, setStartAt] = useState(-1)           // index into `sections`, or -1 for the top of the song
  const [guideOn, setGuideOn] = useState(false)
  const [guideLevel, setGuideLevel] = useState(0.5)
  const [practising, setPractising] = useState(false)
  const [loadingGuide, setLoadingGuide] = useState(false)
  const playerRef = useRef<SessionPlayer | null>(null)
  const placementRef = useRef<TakePlacement | null>(null)
  const pendingRef = useRef(false)

  const player = () => (playerRef.current ??= new SessionPlayer())
  useEffect(() => () => playerRef.current?.close(), [])
  // Decode the beat and guide ahead of time so recording starts without a wait.
  useEffect(() => {
    if (beatUrl) player().load(beatUrl).catch(() => {})
    if (guideUrl) player().load(guideUrl).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [beatUrl, guideUrl])

  // Best-effort headphone guess from output device names; the person can always change it.
  useEffect(() => {
    if (!navigator.mediaDevices?.enumerateDevices) return
    navigator.mediaDevices.enumerateDevices().then((devices) => {
      const outputs = devices.filter((d) => d.kind === "audiooutput")
      if (outputs.some((d) => /head|airpod|earbud|bluetooth/i.test(d.label))) setHeadphones(true)
    })
  }, [])

  // When a recording finishes, hand the blob up with where it sits against the beat
  useEffect(() => {
    if (!pendingRef.current || !recorder.audioBlob) return
    pendingRef.current = false
    onRecorded(recorder.audioBlob, recorder.fileExtension, placementRef.current, withBeat && beatUrl ? headphones : null)
    recorder.reset()
  }, [recorder.audioBlob, recorder.fileExtension, onRecorded, recorder, headphones, withBeat, beatUrl])

  const section = startAt >= 0 ? sections[startAt] : undefined
  const sectionStart = section?.start ?? 0
  const bar = 4 * secondsPerBeat
  // Count-in: one bar of the beat before the part, or four clicks at the very top of the song.
  const playFrom = Math.max(0, sectionStart - bar)
  const clicks = sectionStart - bar < 0 ? 4 : 0

  async function toggleGuide() {
    if (guideOn) {
      setGuideOn(false)
      return
    }
    if (!guideUrl) {
      setLoadingGuide(true)
      try {
        await onWantGuide()
      } finally {
        setLoadingGuide(false)
      }
    }
    setGuideOn(true)
  }

  async function practise() {
    if (!beatUrl) return
    // Nothing else may play while the person is singing along (it would end up in the mic).
    useAudio.getState().pause()
    if (practising) {
      player().stop()
      setPractising(false)
      return
    }
    setPractising(true)
    await player().play(beatUrl, guideOn ? guideUrl : null, {
      from: sectionStart,
      loopTo: section?.end ?? null,
      secondsPerBeat,
      guideLevel,
    })
  }

  async function startRecording() {
    useAudio.getState().pause()
    player().stop()
    setPractising(false)
    await recorder.start()
    placementRef.current = null
    if (withBeat && beatUrl) {
      const beatStarts = await player().play(beatUrl, guideOn ? guideUrl : null, {
        from: playFrom,
        clicks,
        secondsPerBeat,
        guideLevel,
      })
      const startedAt = recorder.getStartedAt()
      if (beatVersionId && startedAt !== null) {
        placementRef.current = {
          beat_version_id: beatVersionId,
          beat_offset_s: playFrom,
          lead_in_s: (beatStarts - startedAt) / 1000,
        }
      }
    }
  }

  function stopRecording() {
    pendingRef.current = true
    recorder.stop()
    player().stop()
  }

  const isRecording = recorder.status === "recording"
  const showOptions = beatUrl && !isRecording && !uploading

  return (
    <div className="flex flex-col items-center gap-5">
      {beatUrl && withBeat && !headphones && (
        <div className="flex items-center gap-2 rounded-md bg-raised px-3 py-2 text-sm text-ink-2" role="status">
          <Headphones className="h-3.5 w-3.5" />
          Use headphones so the beat doesn&apos;t get into your mic. If it does, I can take it out afterwards.
        </div>
      )}

      {showOptions && sections.length > 0 && withBeat && (
        <div className="flex flex-wrap items-center justify-center gap-2" role="group" aria-label="Where to start singing">
          <span className="text-sm text-ink-2">Start from</span>
          <select
            value={startAt}
            onChange={(e) => setStartAt(Number(e.target.value))}
            className="rounded-md border border-line bg-raised px-2 py-1.5 text-sm text-ink"
            aria-label="Start from"
          >
            <option value={-1}>the very start</option>
            {sections.map((s, i) => (
              <option key={s.index} value={i}>
                {s.label}
              </option>
            ))}
          </select>
          <Button variant="outline" size="sm" className={practising ? "border-voice bg-raised text-ink hover:bg-raised" : "border-line text-ink-2 hover:text-ink"} onClick={practise} aria-pressed={practising}>
            <Repeat className="h-3.5 w-3.5" />
            {practising ? "Stop practising" : section ? `Practise ${section.label.toLowerCase()} on repeat` : "Practise"}
          </Button>
        </div>
      )}

      <button
        onClick={isRecording ? stopRecording : startRecording}
        disabled={uploading}
        className={cn(
          "flex h-24 w-24 items-center justify-center rounded-full transition-all",
          // Recording is the one thing that is "live": it gets the voice colour and a square to stop. No pulsing.
          isRecording ? "bg-voice text-ground" : "bg-frank text-ground hover:bg-frank/90",
          uploading && "opacity-60",
        )}
        aria-label={isRecording ? "Stop recording" : "Start recording"}
      >
        {uploading ? <Loader2 className="h-8 w-8 animate-spin" /> : isRecording ? <Square className="h-8 w-8 fill-current" /> : <Mic className="h-9 w-9" />}
      </button>

      {isRecording ? (
        <div className="flex flex-col items-center gap-2">
          <span className="text-base font-medium tabular-nums text-ink" role="timer">Recording · {formatTime(recorder.durationSeconds)}</span>
          <div className="flex h-2 w-40 items-center gap-[2px]" aria-hidden>
            {Array.from({ length: 20 }).map((_, i) => (
              <div key={i} className={cn("h-full flex-1 rounded-[1px] transition-colors", i / 20 < recorder.inputLevel ? "bg-voice" : "bg-raised")} />
            ))}
          </div>
          {withBeat && beatUrl && (
            <p className="text-sm text-ink-2">
              {clicks ? "Four clicks, then the music." : "One bar of the music, then you're on."}
            </p>
          )}
        </div>
      ) : (
        <p className="max-w-xs text-center text-base text-ink-2" role="status">
          {uploading
            ? "Saving your take…"
            : recorder.status === "requesting"
              ? "Waiting for your microphone. If your browser asks, choose Allow."
              : "Press to record"}
        </p>
      )}

      {showOptions && (
        <div className="flex flex-wrap justify-center gap-2">
          <Button variant="outline" size="sm" aria-pressed={withBeat} className={withBeat ? "border-voice bg-raised text-ink hover:bg-raised" : "border-line text-ink-2 hover:text-ink"} onClick={() => setWithBeat(true)}>
            Sing with the beat
          </Button>
          <Button variant="outline" size="sm" aria-pressed={!withBeat} className={!withBeat ? "border-voice bg-raised text-ink hover:bg-raised" : "border-line text-ink-2 hover:text-ink"} onClick={() => setWithBeat(false)}>
            Just my voice
          </Button>
        </div>
      )}

      {showOptions && withBeat && (
        <div className="flex flex-wrap items-center justify-center gap-3 text-sm text-ink-2">
          <Button variant="outline" size="sm" className={guideOn ? "border-voice bg-raised text-ink hover:bg-raised" : "border-line text-ink-2 hover:text-ink"} onClick={toggleGuide} disabled={loadingGuide} aria-pressed={guideOn}>
            {loadingGuide ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Music2 className="h-3.5 w-3.5" />}
            Sing along with the tune
          </Button>
          {guideOn && guideUrl && (
            <label className="flex items-center gap-2">
              Tune volume
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={guideLevel}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  setGuideLevel(v)
                  playerRef.current?.setGuideLevel(v)
                }}
                aria-label="How loud the tune plays"
              />
            </label>
          )}
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={headphones} onChange={(e) => setHeadphones(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--voice))]" />
            I&apos;m wearing headphones
          </label>
        </div>
      )}
      {guideNote && showOptions && <p className="max-w-sm text-center text-sm text-ink-2">{guideNote}</p>}

      {recorder.error && <p className="text-sm text-problem" role="alert">{recorder.error}</p>}
    </div>
  )
}
