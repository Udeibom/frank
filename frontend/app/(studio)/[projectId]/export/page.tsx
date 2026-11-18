"use client"

/**
 * Export Room — the finish line (finish-and-intent spec 11). Before the first download Frank plays the song and
 * asks, in the person's own words, whether it matches what they described. Then the finishing step (ready to
 * share), heard before and after, the download, separate parts, and one optional surprise idea.
 */

import { useEffect, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Waveform } from "@/components/audio/Waveform"
import { createExport, listExports, getDownloadInfo, type ExportRecord } from "@/lib/api/export"
import { listMixVersions, type MixVersion } from "@/lib/api/mix"
import { setActiveBeatVersion } from "@/lib/api/beat"
import {
  answerIntent,
  getIntent,
  makeSurprise,
  separatePartsZip,
  skipSurprise as skipSurpriseApi,
  surpriseOffered,
  type IntentState,
  type SurpriseResult,
} from "@/lib/api/finish"
import { pollJob } from "@/lib/api/jobs"
import { useProjectStore } from "@/store/project"
import { Play, Pause, Download, Sparkles, Loader2, Check, Package, Lightbulb } from "lucide-react"
import { cn } from "@/lib/utils"

type Which = "finished" | "as_mixed"

interface Finished {
  exportId: string
  url: string
  beforeUrl: string | null
  waveform: number[]
  onTarget: boolean | null
}

export default function ExportRoomPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.projectId as string
  const { activeState, updateActiveState } = useProjectStore()

  const [activeMix, setActiveMix] = useState<MixVersion | null>(null)
  const [exports, setExports] = useState<ExportRecord[]>([])
  const [loadError, setLoadError] = useState(false)
  const [intent, setIntent] = useState<IntentState | null>(null)
  const [notYet, setNotYet] = useState(false)
  const [said, setSaid] = useState("")
  const [finished, setFinished] = useState<Finished | null>(null)
  const [which, setWhich] = useState<Which>("finished")
  const [working, setWorking] = useState<string | null>(null)
  const [downloaded, setDownloaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [surpriseState, setSurpriseState] = useState<"hidden" | "offer" | "making" | "ready" | "done">("hidden")
  const [surprise, setSurprise] = useState<SurpriseResult | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    Promise.all([listMixVersions(projectId), listExports(projectId), getIntent(projectId).catch(() => null)])
      .then(([mixes, exps, it]) => {
        const active = mixes.find((m) => m.id === activeState?.active_mix_id) ?? mixes[0] ?? null
        setActiveMix(active)
        setExports(exps)
        setIntent(it)
      })
      .catch(() => setLoadError(true))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  const currentUrl = finished ? (which === "finished" ? finished.url : finished.beforeUrl ?? finished.url) : activeMix?.render_url ?? null

  // One player; switching between "as mixed" and "finished" keeps the moment, so the difference is easy to hear.
  useEffect(() => {
    const at = audioRef.current?.currentTime ?? 0
    const wasPlaying = playing
    audioRef.current?.pause()
    if (!currentUrl) {
      audioRef.current = null
      return
    }
    const audio = new Audio(currentUrl)
    audio.addEventListener("timeupdate", () => audio.duration && setProgress(audio.currentTime / audio.duration))
    audio.addEventListener("ended", () => setPlaying(false))
    audio.addEventListener("loadedmetadata", () => {
      audio.currentTime = Math.min(at, audio.duration || at)
      if (wasPlaying) audio.play().catch(() => setPlaying(false))
    })
    audioRef.current = audio
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

  function seek(f: number) {
    const audio = audioRef.current
    if (audio?.duration) {
      audio.currentTime = f * audio.duration
      setProgress(f)
    }
  }

  const needsIntentCheck = Boolean(activeMix) && exports.length === 0 && intent !== null && intent.answered !== "yes"

  async function sayYes() {
    await answerIntent(projectId, true)
    setIntent((i) => (i ? { ...i, answered: "yes" } : i))
  }

  async function sayNotYet() {
    const reply = await answerIntent(projectId, false, said)
    if (reply.next === "refine") router.push(`/${projectId}/mix?refine=${encodeURIComponent(reply.concern ?? said)}`)
  }

  async function finish() {
    if (!activeMix) return
    setWorking("Finishing your song: making it ready to share. This usually takes about a minute…")
    setError(null)
    try {
      const { job_id } = await createExport(projectId, activeMix.id, true)
      const done = await pollJob(job_id)
      const r = done.result as { export_id: string; audio_url: string; before_url?: string | null; waveform?: number[]; finish?: { on_target?: boolean } }
      setFinished({ exportId: r.export_id, url: r.audio_url, beforeUrl: r.before_url ?? null, waveform: r.waveform ?? [], onTarget: r.finish?.on_target ?? null })
      setWhich("finished")
      setExports(await listExports(projectId))
      surpriseOffered(projectId).then((s) => setSurpriseState(s.offered ? "done" : "offer")).catch(() => {})
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Frank couldn't finish it just then. Want to try again?")
    } finally {
      setWorking(null)
    }
  }

  async function download() {
    if (!finished) return
    setError(null)
    try {
      let id = finished.exportId
      if (which === "as_mixed") {
        const { job_id } = await createExport(projectId, activeMix!.id, false)
        id = ((await pollJob(job_id)).result as { export_id: string }).export_id
      }
      const info = await getDownloadInfo(projectId, id)
      clickDownload(info.url, info.filename)
      setDownloaded(true)
    } catch {
      setError("Something went wrong preparing your download. Want to try again?")
    }
  }

  async function downloadParts() {
    setWorking("Putting the separate parts together. If the music hasn't been split into parts yet, this takes a few minutes…")
    setError(null)
    try {
      const r = await separatePartsZip(projectId)
      clickDownload(r.zip_url, "separate-parts.zip")
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Frank couldn't put the parts together. Want to try again?")
    } finally {
      setWorking(null)
    }
  }

  async function showSurprise() {
    setSurpriseState("making")
    try {
      setSurprise(await makeSurprise(projectId))
      setSurpriseState("ready")
    } catch (err) {
      setError(err instanceof Error ? err.message : null)
      setSurpriseState("done")
    }
  }

  async function skipSurprise() {
    setSurpriseState("done")
    await skipSurpriseApi(projectId).catch(() => {})
  }

  async function chooseSurprise() {
    if (!surprise) return
    await setActiveBeatVersion(projectId, surprise.beat_version_id)
    updateActiveState({ active_beat_version_id: surprise.beat_version_id })
    router.push(`/${projectId}/mix`)
  }

  function clickDownload(url: string, filename: string) {
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
        <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">Frank had trouble loading your song just now. Try refreshing in a moment.</p>
      </div>
    )
  }

  if (!activeMix) {
    return (
      <div className="flex h-screen items-center justify-center px-8 text-center">
        <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
          Once you&apos;ve got a mix you like, come back here to take your song with you. Head to the Mix Room to put it together.
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col items-center overflow-y-auto px-8 py-12">
      <div className="flex w-full max-w-lg flex-col items-center gap-7 text-center">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Here&apos;s your song</h1>
          <p className="mt-2 text-sm text-muted-foreground">Take a final listen before you take it with you.</p>
        </div>

        <button
          onClick={togglePlay}
          className="flex h-20 w-20 items-center justify-center rounded-full bg-primary text-primary-foreground transition-transform hover:scale-105"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? <Pause className="h-8 w-8" /> : <Play className="h-9 w-9 translate-x-0.5" />}
        </button>

        {finished && <Waveform points={finished.waveform} progress={progress} onSeek={seek} />}

        {needsIntentCheck ? (
          <section aria-label="Does it match?" className="w-full rounded-xl border border-primary/30 bg-card p-5 text-left">
            <p className="mb-4 text-sm text-foreground">{intent!.question}</p>
            {!notYet ? (
              <div className="flex gap-2">
                <Button onClick={sayYes}>
                  <Check className="h-4 w-4" /> Yes, that&apos;s it
                </Button>
                <Button variant="outline" onClick={() => setNotYet(true)}>
                  Not yet
                </Button>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <label className="text-xs text-muted-foreground" htmlFor="what-missing">
                  What&apos;s missing, in your own words? (You can leave it blank.)
                </label>
                <input
                  id="what-missing"
                  value={said}
                  onChange={(e) => setSaid(e.target.value)}
                  className="rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="It should feel lonelier…"
                  autoFocus
                />
                <Button onClick={sayNotYet} className="self-start">
                  Find a few ideas
                </Button>
              </div>
            )}
          </section>
        ) : !finished ? (
          <Button size="lg" onClick={finish} disabled={Boolean(working)} className="gap-2 px-8">
            {working ? <Loader2 className="h-5 w-5 animate-spin" /> : <Sparkles className="h-5 w-5" />}
            Finish it, ready to share
          </Button>
        ) : (
          <>
            <div className="flex gap-2" role="group" aria-label="Compare before and after">
              <Button variant={which === "as_mixed" ? "default" : "outline"} size="sm" onClick={() => setWhich("as_mixed")} disabled={!finished.beforeUrl}>
                As you mixed it
              </Button>
              <Button variant={which === "finished" ? "default" : "outline"} size="sm" onClick={() => setWhich("finished")}>
                Finished
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              {finished.onTarget === false
                ? "I got it close to the loudness songs usually have, but not all the way. It's still safe to share."
                : "The finished one plays as loud as songs on streaming apps, with no harsh peaks. Pick the one you prefer."}
            </p>
            <Button size="lg" onClick={download} className="gap-2 px-8">
              <Download className="h-5 w-5" /> Download {which === "finished" ? "the finished song" : "it as you mixed it"}
            </Button>
          </>
        )}

        {finished && (
          <Button variant="outline" size="sm" onClick={downloadParts} disabled={Boolean(working)} className="gap-2">
            <Package className="h-4 w-4" /> Download separate parts
          </Button>
        )}

        {working && (
          <p className="flex items-center gap-2 text-xs text-muted-foreground" role="status">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> {working}
          </p>
        )}
        {error && <p className="text-xs text-red-400">{error}</p>}
        {downloaded && !error && <p className="text-sm text-primary/80">It&apos;s yours. Good luck with it.</p>}

        {surpriseState === "offer" && (
          <section aria-label="One idea" className="w-full rounded-xl border border-border bg-card p-4 text-left">
            <p className="mb-3 flex items-center gap-2 text-sm text-foreground">
              <Lightbulb className="h-4 w-4 text-primary" /> Before we finish, I tried one idea. Want to hear it? Your version stays exactly as it is.
            </p>
            <div className="flex gap-2">
              <Button size="sm" onClick={showSurprise}>Show me</Button>
              <Button size="sm" variant="outline" onClick={skipSurprise}>No thanks</Button>
            </div>
          </section>
        )}
        {surpriseState === "making" && (
          <p className="flex items-center gap-2 text-xs text-muted-foreground" role="status">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Making my idea. This takes a few minutes; your song is already safe.
          </p>
        )}
        {surpriseState === "ready" && surprise && (
          <section aria-label="Frank's idea" className="w-full rounded-xl border border-primary/30 bg-card p-4 text-left">
            <p className="mb-1 text-sm font-medium text-foreground">{surprise.title}</p>
            <p className="mb-3 text-xs text-muted-foreground">{surprise.plain}</p>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => new Audio(surprise.render_url).play().catch(() => {})}>
                <Play className="h-3.5 w-3.5" /> Hear it
              </Button>
              <Button size="sm" onClick={chooseSurprise}>Use this one instead</Button>
              <Button size="sm" variant="outline" onClick={() => setSurpriseState("done")}>Keep mine</Button>
            </div>
          </section>
        )}

        {exports.length > 0 && (
          <div className="mt-4 w-full border-t border-border pt-4">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Past downloads</p>
            <div className="flex flex-col gap-1.5">
              {exports.map((e) => (
                <button
                  key={e.id}
                  onClick={async () => {
                    const info = await getDownloadInfo(projectId, e.id)
                    clickDownload(info.url, info.filename)
                  }}
                  className={cn("flex items-center justify-between rounded-md px-3 py-2 text-left text-xs hover:bg-secondary")}
                >
                  <span className="text-muted-foreground">
                    {new Date(e.created_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
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
