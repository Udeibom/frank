"use client"

/**
 * TexturePlayer — plays a Feel Lab texture inline in the conversation.
 * Auto-plays when it arrives, shows a simple animated bar visualization,
 * and lets the user replay it. Playback only — no audio processing.
 */

import { useEffect, useRef, useState } from "react"
import { Play, Pause } from "lucide-react"
import { cn } from "@/lib/utils"

interface TexturePlayerProps {
  audioUrl: string
  autoPlay?: boolean
}

export function TexturePlayer({ audioUrl, autoPlay = true }: TexturePlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  // Textures play through, loop exactly once, then stop (spec R2).
  const loopedRef = useRef(false)

  useEffect(() => {
    const audio = new Audio(audioUrl)
    audioRef.current = audio
    loopedRef.current = false

    const onTime = () => {
      if (audio.duration) setProgress(audio.currentTime / audio.duration)
    }
    const onEnd = () => {
      if (!loopedRef.current) {
        // First finish — replay once
        loopedRef.current = true
        audio.currentTime = 0
        audio.play().catch(() => setPlaying(false))
      } else {
        setPlaying(false)
        setProgress(0)
      }
    }
    audio.addEventListener("timeupdate", onTime)
    audio.addEventListener("ended", onEnd)

    if (autoPlay) {
      audio.play().then(() => setPlaying(true)).catch(() => {
        // Autoplay may be blocked; user can press play
        setPlaying(false)
      })
    }

    return () => {
      audio.pause()
      audio.removeEventListener("timeupdate", onTime)
      audio.removeEventListener("ended", onEnd)
      audioRef.current = null
    }
  }, [audioUrl, autoPlay])

  function toggle() {
    const audio = audioRef.current
    if (!audio) return
    if (playing) {
      audio.pause()
      setPlaying(false)
    } else {
      audio.play().then(() => setPlaying(true)).catch(() => {})
    }
  }

  // Simple bar visualization — animates while playing
  const bars = 28

  return (
    <div className="flex w-full max-w-[90%] items-center gap-3 rounded-xl border border-primary/20 bg-primary/5 p-3">
      <button
        onClick={toggle}
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-transform hover:scale-105"
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? (
          <Pause className="h-4 w-4" />
        ) : (
          <Play className="h-4 w-4 translate-x-0.5" />
        )}
      </button>

      <div className="flex flex-1 items-center gap-[2px]">
        {Array.from({ length: bars }).map((_, i) => {
          const active = i / bars <= progress
          return (
            <div
              key={i}
              className={cn(
                "flex-1 rounded-full transition-all duration-150",
                active ? "bg-primary" : "bg-primary/20",
              )}
              style={{
                height: `${
                  8 + Math.abs(Math.sin((i / bars) * Math.PI * 2)) * 18
                }px`,
                opacity: playing && active ? 1 : 0.7,
              }}
            />
          )
        })}
      </div>
    </div>
  )
}
