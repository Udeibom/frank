"use client"

/**
 * VersionChoice — when "give me that version back" could mean two versions, Frank plays both and lets the
 * person pick (spec 08, requirement 5.2).
 */

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import type { VersionCandidate } from "@/types/api"
import { Play, Pause, X } from "lucide-react"

interface VersionChoiceProps {
  candidates: VersionCandidate[]
  onPick: (versionId: string) => void
  onClose: () => void
}

export function VersionChoice({ candidates, onPick, onClose }: VersionChoiceProps) {
  const [playing, setPlaying] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  useEffect(() => () => audioRef.current?.pause(), [])

  function toggle(c: VersionCandidate) {
    if (!c.render_url) return
    audioRef.current?.pause()
    if (playing === c.id) {
      setPlaying(null)
      return
    }
    const audio = new Audio(c.render_url)
    audio.onended = () => setPlaying(null)
    audioRef.current = audio
    audio.play().then(() => setPlaying(c.id)).catch(() => setPlaying(null))
  }

  return (
    <section aria-label="Which version did you mean?" className="rounded-xl border border-primary/30 bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-medium text-foreground">Which one did you mean?</p>
        <button onClick={onClose} aria-label="Close" className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="flex flex-col gap-2">
        {candidates.map((c) => (
          <div key={c.id} className="flex items-center gap-3 rounded-lg border border-border px-3 py-2">
            <button
              onClick={() => toggle(c)}
              aria-label={playing === c.id ? `Pause ${c.label ?? "version"}` : `Play ${c.label ?? "version"}`}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-primary hover:bg-primary/25"
            >
              {playing === c.id ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5 translate-x-px" />}
            </button>
            <span className="flex-1 truncate text-sm text-foreground">{c.label ?? "Version"}</span>
            <Button size="sm" variant="outline" onClick={() => onPick(c.id)}>
              This one
            </Button>
          </div>
        ))}
      </div>
    </section>
  )
}
