"use client"

/**
 * HumButton — lets the user hum a melody or vibe into the Feel Lab.
 * Records in the browser, sends to the backend for analysis. The analysis
 * seeds the musical direction. Records only — no processing on the client.
 */

import { useEffect, useRef, useState } from "react"
import { useRecorder } from "@/hooks/useRecorder"
import { analyzeHum, type HumAnalysisResult } from "@/lib/api/feel"
import { Music, Square, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"

interface HumButtonProps {
  projectId: string
  onAnalyzed: (result: HumAnalysisResult) => void
  onError?: (message: string) => void
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, "0")}`
}

export function HumButton({ projectId, onAnalyzed, onError }: HumButtonProps) {
  const recorder = useRecorder()
  const [analyzing, setAnalyzing] = useState(false)
  const pendingUpload = useRef(false)

  useEffect(() => {
    if (!pendingUpload.current || !recorder.audioBlob) return
    pendingUpload.current = false
    const blob = recorder.audioBlob
    const ext = recorder.fileExtension

    setAnalyzing(true)
    analyzeHum(projectId, blob, ext)
      .then((result) => onAnalyzed(result))
      .catch(() =>
        onError?.("Couldn't quite catch that hum — want to try again?"),
      )
      .finally(() => {
        setAnalyzing(false)
        recorder.reset()
      })
  }, [recorder.audioBlob, recorder.fileExtension, projectId, onAnalyzed, onError, recorder])

  if (analyzing) {
    return (
      <Button variant="ghost" size="sm" disabled className="w-full justify-start">
        <Loader2 className="h-4 w-4 animate-spin" />
        Listening to your hum…
      </Button>
    )
  }

  if (recorder.status === "recording") {
    return (
      <Button
        variant="ghost"
        size="sm"
        onClick={() => {
          pendingUpload.current = true
          recorder.stop()
        }}
        className="w-full justify-start text-destructive hover:text-destructive"
      >
        <Square className="h-4 w-4 fill-current" />
        Stop humming ({formatTime(recorder.durationSeconds)})
      </Button>
    )
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => recorder.start()}
      className="w-full justify-start text-muted-foreground"
    >
      <Music className="h-4 w-4" />
      Hum how it should go
    </Button>
  )
}
