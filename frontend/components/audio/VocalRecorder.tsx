"use client"

/**
 * VocalRecorder — the centerpiece of the Voice Room. A large, unmistakable
 * record button with a live level meter and timer. Can play the beat through
 * (for singing along) and warns — but never blocks — if headphones aren't
 * detected, so the beat doesn't bleed into the mic. Records only; all
 * processing happens on the backend.
 */

import { useEffect, useRef, useState } from "react"
import { useRecorder } from "@/hooks/useRecorder"
import { Button } from "@/components/ui/button"
import { Mic, Square, Loader2, Headphones } from "lucide-react"
import { cn } from "@/lib/utils"

interface VocalRecorderProps {
  beatUrl: string | null
  uploading: boolean
  onRecorded: (blob: Blob, fileExtension: string) => void
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

export function VocalRecorder({
  beatUrl,
  uploading,
  onRecorded,
}: VocalRecorderProps) {
  const recorder = useRecorder()
  const [withBeat, setWithBeat] = useState(true)
  const [likelyHeadphones, setLikelyHeadphones] = useState<boolean | null>(null)
  const beatAudioRef = useRef<HTMLAudioElement | null>(null)
  const pendingRef = useRef(false)

  // Best-effort headphone detection via output device labels
  useEffect(() => {
    if (!navigator.mediaDevices?.enumerateDevices) return
    navigator.mediaDevices.enumerateDevices().then((devices) => {
      const outputs = devices.filter((d) => d.kind === "audiooutput")
      const headphoneLike = outputs.some((d) =>
        /head|airpod|earbud|bluetooth/i.test(d.label),
      )
      // Only claim headphones if we actually see a matching label
      setLikelyHeadphones(headphoneLike ? true : null)
    })
  }, [])

  // When a recording finishes, hand the blob up
  useEffect(() => {
    if (!pendingRef.current || !recorder.audioBlob) return
    pendingRef.current = false
    onRecorded(recorder.audioBlob, recorder.fileExtension)
    recorder.reset()
  }, [recorder.audioBlob, recorder.fileExtension, onRecorded, recorder])

  async function startRecording() {
    // Play the beat along with recording if requested
    if (withBeat && beatUrl) {
      const beat = new Audio(beatUrl)
      beat.currentTime = 0
      beatAudioRef.current = beat
      beat.play().catch(() => {})
    }
    await recorder.start()
  }

  function stopRecording() {
    pendingRef.current = true
    recorder.stop()
    beatAudioRef.current?.pause()
  }

  const isRecording = recorder.status === "recording"

  return (
    <div className="flex flex-col items-center gap-5">
      {/* Headphone tip — informs, never blocks */}
      {beatUrl && withBeat && likelyHeadphones !== true && (
        <div className="flex items-center gap-2 rounded-full bg-amber-500/10 px-4 py-1.5 text-xs text-amber-200/80">
          <Headphones className="h-3.5 w-3.5" />
          Use headphones so the beat doesn&apos;t get picked up by your mic
        </div>
      )}

      {/* The record button */}
      <button
        onClick={isRecording ? stopRecording : startRecording}
        disabled={uploading}
        className={cn(
          "flex h-24 w-24 items-center justify-center rounded-full transition-all",
          isRecording
            ? "bg-red-500 text-white scale-105 animate-pulse-amber"
            : "bg-primary text-primary-foreground hover:scale-105",
          uploading && "opacity-60",
        )}
        aria-label={isRecording ? "Stop recording" : "Start recording"}
      >
        {uploading ? (
          <Loader2 className="h-8 w-8 animate-spin" />
        ) : isRecording ? (
          <Square className="h-8 w-8 fill-current" />
        ) : (
          <Mic className="h-9 w-9" />
        )}
      </button>

      {/* Timer + level meter while recording */}
      {isRecording ? (
        <div className="flex flex-col items-center gap-2">
          <span className="text-sm font-medium text-foreground tabular-nums">
            {formatTime(recorder.durationSeconds)}
          </span>
          <div className="flex h-2 w-40 items-center gap-[2px]">
            {Array.from({ length: 20 }).map((_, i) => (
              <div
                key={i}
                className={cn(
                  "h-full flex-1 rounded-full transition-colors",
                  i / 20 < recorder.inputLevel
                    ? "bg-primary"
                    : "bg-muted",
                )}
              />
            ))}
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          {uploading ? "Saving your take…" : "Tap to record"}
        </p>
      )}

      {/* Record-with-beat toggle */}
      {beatUrl && !isRecording && !uploading && (
        <div className="flex gap-2">
          <Button
            variant={withBeat ? "default" : "outline"}
            size="sm"
            onClick={() => setWithBeat(true)}
          >
            Sing with the beat
          </Button>
          <Button
            variant={!withBeat ? "default" : "outline"}
            size="sm"
            onClick={() => setWithBeat(false)}
          >
            Just my voice
          </Button>
        </div>
      )}

      {recorder.error && (
        <p className="text-xs text-red-400">{recorder.error}</p>
      )}
    </div>
  )
}
