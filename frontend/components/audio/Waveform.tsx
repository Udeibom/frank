"use client"

/**
 * Waveform (frankenstein spec 14, requirement 8.1): the shape of a sound, drawn by WaveSurfer from peaks the server
 * measured, with optional regions (the lines of a take). The browser never decodes or processes the audio: the
 * shape comes from the backend, and the sound plays through the one AudioEngine (store/audio.ts).
 *
 * Clicking the shape plays from there. A region plays just that line and stops at its end.
 */

import { useEffect, useRef, useState } from "react"
import WaveSurfer from "wavesurfer.js"
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.esm.js"
import { soundPeaks } from "@/lib/api/organs"
import { useAudio, usePlayback, type Track } from "@/store/audio"

export interface WaveRegion {
  start: number
  end: number
  label: string
}

interface WaveformProps {
  projectId: string
  track: Track
  regions?: WaveRegion[]
  height?: number
  /** Called when a region is chosen, e.g. to offer "sing this line again". */
  onRegion?: (index: number) => void
}

const COLOUR: Record<Track["material"], string> = {
  words: "rgb(216 203 176 / 0.55)",
  feel: "rgb(var(--feel) / 0.55)",
  music: "rgb(var(--music) / 0.55)",
  voice: "rgb(var(--voice) / 0.55)",
}

export function Waveform({ projectId, track, regions = [], height = 56, onRegion }: WaveformProps) {
  const box = useRef<HTMLDivElement>(null)
  const ws = useRef<WaveSurfer | null>(null)
  const [seconds, setSeconds] = useState(0)
  const [failed, setFailed] = useState(false)
  const stopAt = useRef<number | null>(null)
  const { isCurrent, playing, position } = usePlayback(track.id)
  const play = useAudio((s) => s.play)
  const pause = useAudio((s) => s.pause)

  useEffect(() => {
    let cancelled = false
    setFailed(false)
    soundPeaks(projectId, track.url)
      .then(({ peaks, seconds: len }) => {
        if (cancelled || !box.current || !peaks.length) return
        setSeconds(len)
        const regionsPlugin = RegionsPlugin.create()
        const w = WaveSurfer.create({
          container: box.current,
          peaks: [peaks],
          duration: len,
          height,
          waveColor: getComputedStyle(box.current).getPropertyValue("--wave") || "rgb(150 141 127 / 0.6)",
          progressColor: "transparent",
          cursorWidth: 0,
          barWidth: 2,
          barGap: 1,
          barRadius: 2,
          interact: true,
          normalize: false,
          plugins: [regionsPlugin],
        })
        w.on("interaction", (t: number) => {
          stopAt.current = null
          void play(track, { at: t })
        })
        w.on("ready", () => {
          regions.forEach((r, i) => {
            const region = regionsPlugin.addRegion({
              start: r.start,
              end: r.end,
              content: r.label.length > 28 ? `${r.label.slice(0, 27)}…` : r.label,
              color: COLOUR[track.material],
              drag: false,
              resize: false,
            })
            region.on("click", (e: MouseEvent) => {
              e.stopPropagation()
              stopAt.current = r.end
              onRegion?.(i)
              void play(track, { at: r.start })
            })
          })
        })
        ws.current = w
      })
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
      ws.current?.destroy()
      ws.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- redraw only when the sound itself changes
  }, [projectId, track.url, track.id, height, regions.length])

  // A line plays to its end, then stops.
  useEffect(() => {
    if (isCurrent && playing && stopAt.current !== null && position >= stopAt.current) {
      stopAt.current = null
      pause()
    }
  }, [isCurrent, playing, position, pause])

  const at = isCurrent && seconds > 0 ? Math.min(1, position / seconds) : null
  return (
    <div className="relative w-full" aria-label={`The shape of ${track.label}. Click to play from any point.`} role="img">
      {failed && <p className="text-xs text-ink-3">I couldn&apos;t draw this one. It still plays.</p>}
      <div ref={box} className="w-full" style={{ minHeight: failed ? 0 : height }} />
      {at !== null && (
        <span aria-hidden className="pointer-events-none absolute top-0 h-full w-px bg-frank" style={{ left: `${at * 100}%` }} />
      )}
    </div>
  )
}
