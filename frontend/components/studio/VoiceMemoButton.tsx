"use client"

/**
 * VoiceMemoButton — a subtle way to capture a song idea by voice.
 * Records in the browser, sends to the backend for transcription.
 * This is for catching ideas, not recording the final vocal.
 */

import { useEffect, useRef, useState } from "react"
import { useRecorder } from "@/hooks/useRecorder"
import { uploadVoiceMemo } from "@/lib/api/lyrics"
import { Mic, Square, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"

interface VoiceMemoButtonProps {
  projectId: string
  onTranscription: (text: string) => void
  onError?: (message: string) => void
  /** "stage": a real control on the room's stage. "chat": the compact link above the conversation input. */
  appearance?: "chat" | "stage"
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

export function VoiceMemoButton({
  projectId,
  onTranscription,
  onError,
  appearance = "chat",
}: VoiceMemoButtonProps) {
  const look = appearance === "stage" ? "h-11 rounded-lg border border-line bg-surface-high px-5 text-label-md text-on-surface hover:bg-surface-highest" : "w-full justify-start"
  const recorder = useRecorder()
  const [transcribing, setTranscribing] = useState(false)
  // Tracks that the user pressed stop and wants the memo transcribed
  const pendingUpload = useRef(false)

  // When a blob becomes available after a requested stop, upload it.
  // Watching the blob via effect avoids stale-closure polling.
  useEffect(() => {
    if (!pendingUpload.current || !recorder.audioBlob) return
    pendingUpload.current = false
    const blob = recorder.audioBlob

    const ext = recorder.fileExtension
    setTranscribing(true)
    uploadVoiceMemo(projectId, blob, ext)
      .then((result) => {
        if (result.transcription) {
          onTranscription(result.transcription)
        } else {
          onError?.("I couldn't make out any words in that — want to try again?")
        }
      })
      .catch(() => {
        onError?.("Something went wrong with that recording — want to try again?")
      })
      .finally(() => {
        setTranscribing(false)
        recorder.reset()
      })
  }, [recorder.audioBlob, recorder.fileExtension, projectId, onTranscription, onError, recorder])

  function handleStart() {
    recorder.start()
  }

  function handleStop() {
    pendingUpload.current = true
    recorder.stop()
  }

  if (transcribing) {
    return (
      <Button variant={appearance === "stage" ? "outline" : "ghost"} size="sm" disabled className={look} role="status">
        <Loader2 className="h-4 w-4 animate-spin" />
        Listening back…
      </Button>
    )
  }

  if (recorder.status === "recording") {
    return (
      <Button
        variant={appearance === "stage" ? "outline" : "ghost"}
        size="sm"
        onClick={handleStop}
        className={`${look} text-problem hover:text-problem`}
      >
        <Square className="h-4 w-4 fill-current" />
        Stop ({formatTime(recorder.durationSeconds)})
      </Button>
    )
  }

  return (
    <Button
      variant={appearance === "stage" ? "outline" : "ghost"}
      size="sm"
      onClick={handleStart}
      className={appearance === "stage" ? look : "w-full justify-start text-muted-foreground"}
    >
      <Mic className={appearance === "stage" ? "h-4 w-4 text-words" : "h-4 w-4"} />
      Record voice memo — speak or sing and Frank will transcribe it
    </Button>
  )
}
