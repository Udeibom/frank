"use client"

/**
 * Export Room — the finish line. One last listen, an optional "make it radio
 * ready" pass, and the download. This should feel like the end of a journey,
 * not a checkout page. Frank has been with the user the whole way.
 */

import { useEffect, useRef, useState } from "react"
import { useParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import {
  createExport,
  listExports,
  getDownloadInfo,
  type ExportRecord,
} from "@/lib/api/export"
import { listMixVersions, type MixVersion } from "@/lib/api/mix"
import { pollJob } from "@/lib/api/jobs"
import { useProjectStore } from "@/store/project"
import { Play, Pause, Download, Sparkles, Loader2, RotateCcw, Check } from "lucide-react"
import { cn } from "@/lib/utils"

export default function ExportRoomPage() {
  const params = useParams()
  const projectId = params.projectId as string
  const { activeState } = useProjectStore()

  const [activeMix, setActiveMix] = useState<MixVersion | null>(null)
  const [exports, setExports] = useState<ExportRecord[]>([])
  const [loadError, setLoadError] = useState(false)
  // The audio we're currently offering to download: the mix, or a mastered export
  const [currentUrl, setCurrentUrl] = useState<string | null>(null)
  const [mastered, setMastered] = useState(false)
  const [unmasteredUrl, setUnmasteredUrl] = useState<string | null>(null)

  const [mastering, setMastering] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [downloaded, setDownloaded] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [autoPlay, setAutoPlay] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  // Load the active mix on entry
  useEffect(() => {
    Promise.all([listMixVersions(projectId), listExports(projectId)])
      .then(([mixes, exps]) => {
        const active =
          mixes.find((m) => m.id === activeState?.active_mix_id) ?? mixes[0] ?? null
        setActiveMix(active)
        setCurrentUrl(active?.render_url ?? null)
        setUnmasteredUrl(active?.render_url ?? null)
        setExports(exps)
      })
      .catch(() => setLoadError(true))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  useEffect(() => {
    audioRef.current?.pause()
    setPlaying(false)
    if (!currentUrl) {
      audioRef.current = null
      return
    }
    const audio = new Audio(currentUrl)
    audio.addEventListener("ended", () => setPlaying(false))
    audioRef.current = audio
    // Auto-play when a freshly mastered version arrives (R2)
    if (autoPlay) {
      audio.play().then(() => setPlaying(true)).catch(() => {})
      setAutoPlay(false)
    }
    return () => audio.pause()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentUrl])

  function togglePlay() {
    const audio = audioRef.current
    if (!audio) return
    if (playing) {
      audio.pause()
      setPlaying(false)
    } else {
      audio.play().then(() => setPlaying(true)).catch(() => {})
    }
  }

  async function handleMaster() {
    if (!activeMix) return
    setMastering(true)
    setError(null)
    try {
      const { job_id } = await createExport(projectId, activeMix.id, true)
      const result = await pollJob(job_id)
      const r = result.result as { audio_url?: string }
      if (r?.audio_url) {
        setCurrentUrl(r.audio_url)
        setMastered(true)
        setAutoPlay(true) // play the mastered version when it loads (R2)
      }
      await refreshExports()
    } catch {
      setError("Frank couldn't polish it just then — want to try again?")
    } finally {
      setMastering(false)
    }
  }

  function revertToUnmastered() {
    setCurrentUrl(unmasteredUrl)
    setMastered(false)
  }

  async function refreshExports() {
    setExports(await listExports(projectId))
  }

  async function handleDownload() {
    if (!activeMix) return
    setDownloading(true)
    setError(null)
    try {
      // The backend dedups by (mix version + mastered), so this reuses an
      // existing export if one matches — download stays instant, no dupes.
      const { job_id } = await createExport(projectId, activeMix.id, mastered)
      const result = await pollJob(job_id)
      const exportId = (result.result as { export_id?: string })?.export_id
      if (!exportId) return
      await refreshExports()

      const info = await getDownloadInfo(projectId, exportId)
      triggerBrowserDownload(info.url, info.filename)
      setDownloaded(true)
    } catch {
      setError("Something went wrong preparing your download — want to try again?")
    } finally {
      setDownloading(false)
    }
  }

  function triggerBrowserDownload(url: string, filename: string) {
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  if (loadError) {
    return (
      <div className="flex h-screen items-center justify-center px-8 text-center">
        <p className="max-w-sm text-sm text-muted-foreground leading-relaxed">
          Frank had trouble loading your song just now — try refreshing in a moment.
        </p>
      </div>
    )
  }

  if (!activeMix) {
    return (
      <div className="flex h-screen items-center justify-center px-8 text-center">
        <div className="max-w-sm">
          <p className="text-sm text-muted-foreground leading-relaxed">
            Once you&apos;ve got a mix you like, come back here to take your song
            with you. Head to the Mix Room to put it together.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col items-center justify-center px-8">
      <div className="flex w-full max-w-md flex-col items-center gap-8 text-center">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">
            Here&apos;s your song
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Take a final listen before you take it with you.
          </p>
        </div>

        {/* Play */}
        <button
          onClick={togglePlay}
          className="flex h-20 w-20 items-center justify-center rounded-full bg-primary text-primary-foreground transition-transform hover:scale-105 hover:glow-amber"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? (
            <Pause className="h-8 w-8" />
          ) : (
            <Play className="h-9 w-9 translate-x-0.5" />
          )}
        </button>

        {mastered && (
          <div className="flex items-center gap-2 text-xs text-primary">
            <Check className="h-3.5 w-3.5" />
            Radio-ready version
          </div>
        )}

        {/* Mastering */}
        <div className="flex flex-col items-center gap-3">
          {!mastered ? (
            <Button
              variant="outline"
              onClick={handleMaster}
              disabled={mastering}
              className="gap-2"
            >
              {mastering ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {mastering ? "Polishing your song…" : "Make it radio ready"}
            </Button>
          ) : (
            <button
              onClick={revertToUnmastered}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
            >
              <RotateCcw className="h-3 w-3" />
              Go back to the original
            </button>
          )}
        </div>

        {/* Download */}
        <Button
          size="lg"
          onClick={handleDownload}
          disabled={downloading}
          className="mt-2 gap-2 px-8"
        >
          {downloading ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Download className="h-5 w-5" />
          )}
          {downloading ? "Preparing your download…" : "Download your song"}
        </Button>

        {error && <p className="text-xs text-red-400">{error}</p>}

        {downloaded && !error && (
          <p className="text-sm text-primary/80">
            It&apos;s yours. Good luck with it.
          </p>
        )}

        {/* Export history */}
        {exports.length > 0 && (
          <div className="mt-4 w-full border-t border-border pt-4">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Past downloads
            </p>
            <div className="flex flex-col gap-1.5">
              {exports.map((e) => (
                <button
                  key={e.id}
                  onClick={async () => {
                    const info = await getDownloadInfo(projectId, e.id)
                    triggerBrowserDownload(info.url, info.filename)
                  }}
                  className="flex items-center justify-between rounded-md px-3 py-2 text-left text-xs hover:bg-secondary"
                >
                  <span className="text-muted-foreground">
                    {new Date(e.created_at).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </span>
                  <Download className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
