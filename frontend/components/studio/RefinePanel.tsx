"use client"

/**
 * RefinePanel — "something feels wrong" (spec 08). Frank listens, says what it heard, and offers two or three
 * directions. Each can be heard before choosing, and compared with the song as it is now at the same moment.
 * "Use this" makes it a new version; the earlier one is kept.
 */

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { askForDirections, chooseDirection, disagree, previewDirection } from "@/lib/api/refine"
import { cancelJob, pollJob } from "@/lib/api/jobs"
import type { RefinePreview, RefineProposal } from "@/types/api"
import { Ear, Loader2, Play, Pause, Check, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { useAudio, type Track } from "@/store/audio"

interface RefinePanelProps {
  projectId: string
  room: "beat" | "mix"
  concern: string | null
  /** Bump to start listening (again). */
  startKey: number
  onSay: (text: string) => void
  /** The finished job's result (holds the new version's id). */
  onCommitted: (result: Record<string, unknown> | null) => Promise<void> | void
  onClose: () => void
}

type Side = "now" | "new"

export function RefinePanel({ projectId, room, concern, startKey, onSay, onCommitted, onClose }: RefinePanelProps) {
  const [phase, setPhase] = useState<"listening" | "ready" | "error">("listening")
  const [progress, setProgress] = useState("Listening to your song…")
  const [proposal, setProposal] = useState<RefineProposal | null>(null)
  const [previews, setPreviews] = useState<Record<number, RefinePreview>>({})
  const [loadingPreview, setLoadingPreview] = useState<number | null>(null)
  const [previewText, setPreviewText] = useState("")
  const [committing, setCommitting] = useState<number | null>(null)
  const [chosen, setChosen] = useState<number | null>(null)
  const [disagreeing, setDisagreeing] = useState(false)
  const [said, setSaid] = useState("")
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const jobIdRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const engine = useAudio()
  const trackId = (n: number, side: Side) => `refine:${proposal?.proposal_id ?? ""}:${n}:${side}`
  const playing: { n: number; side: Side } | null = (() => {
    const id = engine.playing ? engine.track?.id : null
    if (!id || !proposal) return null
    for (const n of Object.keys(previews).map(Number)) {
      if (id === trackId(n, "new")) return { n, side: "new" }
      if (id === trackId(n, "now")) return { n, side: "now" }
    }
    return null
  })()

  function rememberJob(id: string) {
    jobIdRef.current = id
    setActiveJobId(id)
  }

  function clearJob() {
    jobIdRef.current = null
    setActiveJobId(null)
    abortRef.current = null
  }

  async function stopActive() {
    const id = jobIdRef.current
    abortRef.current?.abort()
    if (id) await cancelJob(id).catch(() => undefined)
    clearJob()
    setLoadingPreview(null)
    setCommitting(null)
    setPhase((p) => (p === "listening" ? "error" : p))
    setProgress("You stopped that one. Nothing was lost. Ask when you're ready.")
  }

  useEffect(() => {
    if (startKey <= 0) return
    let cancelled = false
    const controller = new AbortController()
    abortRef.current = controller
    setPhase("listening")
    setProgress("Listening to your song… this takes about a minute.")
    setProposal(null)
    setPreviews({})
    setLoadingPreview(null)
    setCommitting(null)
    setChosen(null)
    setDisagreeing(false)
    setSaid("")
    clearJob()
    askForDirections(projectId, concern, room, (t) => !cancelled && setProgress(t), (id) => !cancelled && rememberJob(id), controller.signal)
      .then((p) => {
        if (cancelled) return
        setProposal(p)
        setPhase("ready")
        clearJob()
        onSay(p.message)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setPhase("error")
        setProgress(err instanceof Error ? err.message : "I couldn't listen just now. Want to try again?")
        clearJob()
      })
    return () => {
      cancelled = true
      controller.abort()
      const id = jobIdRef.current
      if (id) void cancelJob(id).catch(() => undefined)
      clearJob()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startKey])

  function stop() {
    if (playing) engine.pause()
  }

  function sideTrack(n: number, side: Side, p: RefinePreview): Track | null {
    const url = side === "new" ? p.preview_url : p.before_url
    if (!url || !proposal) return null
    const title = proposal.directions[n]?.title ?? "This idea"
    return {
      id: trackId(n, side),
      url,
      label: side === "new" ? title : `${title}: as it is now`,
      material: room === "mix" ? "voice" : "music",
      onSong: true,
    }
  }

  /** Play one side; switching sides keeps the same moment, so the difference is easy to hear. */
  function play(n: number, side: Side, p: RefinePreview | undefined = previews[n]) {
    if (!p) return
    const track = sideTrack(n, side, p)
    if (!track) return
    void engine.toggle(track, { keepPosition: playing?.n === n })
  }

  async function hear(n: number) {
    if (!proposal) return
    if (previews[n]) {
      play(n, "new")
      return
    }
    setLoadingPreview(n)
    setPreviewText("Playing it the new way… usually under a minute.")
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const p = await previewDirection(projectId, proposal.proposal_id, n, setPreviewText, rememberJob, controller.signal)
      setPreviews((all) => ({ ...all, [n]: p }))
      play(n, "new", p)
    } catch (err) {
      onSay(err instanceof Error ? err.message : "I couldn't play that idea just now. Want to try again?")
    } finally {
      setLoadingPreview(null)
      clearJob()
    }
  }

  async function use(n: number) {
    if (!proposal) return
    stop()
    setCommitting(n)
    try {
      const res = await chooseDirection(projectId, proposal.proposal_id, n)
      onSay(res.message)
      const done = await pollJob(res.job_id)
      setChosen(n)
      await onCommitted(done.result)
      const changes = (done.result as { changes?: string[] } | null)?.changes ?? []
      onSay(`${changes.length ? changes.join(" ") + " " : ""}It's in. How does that feel? If it's not right, the other ideas are still here.`)
    } catch (err) {
      onSay(err instanceof Error ? err.message : "Frank couldn't make that change. Want to try again?")
    } finally {
      setCommitting(null)
    }
  }

  async function sendDisagree() {
    if (!proposal || !said.trim() || disagreeing) return
    setDisagreeing(true)
    try {
      const res = await disagree(projectId, proposal.proposal_id, said.trim())
      onSay(res.message)
      setSaid("")
      setDisagreeing(false)
    } catch (err) {
      onSay(err instanceof Error ? err.message : "Tell me once more in a moment.")
      setDisagreeing(false)
    }
  }

  return (
    <section aria-label="Ideas to try" className="rounded-md border border-line bg-surface p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-base font-medium text-ink">
          <Ear className="h-4 w-4 text-ink-2" aria-hidden="true" />
          {proposal?.experiment ? "Let your ears decide" : "A few ways to go"}
        </div>
        <button onClick={onClose} aria-label="Close ideas" className="rounded-sm p-1 text-ink-3 hover:text-ink">
          <X className="h-4 w-4" />
        </button>
      </div>

      {phase !== "ready" && (
        <div className="flex items-center gap-2 text-base text-ink-2" role="status">
          {phase === "listening" && <Loader2 className="h-4 w-4 animate-spin" />}
          <span>{progress}</span>
          {phase === "listening" && activeJobId && (
            <button onClick={() => void stopActive()} className="text-sm text-ink-2 underline underline-offset-4 hover:text-ink">
              Stop
            </button>
          )}
        </div>
      )}

      {phase === "ready" && proposal && (
        <div className="flex flex-col gap-3">
          {proposal.findings.length > 0 && (
            <ul className="list-disc pl-5 text-sm text-ink-2">
              {proposal.findings.slice(0, 3).map((f, i) => (
                <li key={i}>{f.plain}</li>
              ))}
            </ul>
          )}
          <div className="grid gap-3 md:grid-cols-3">
            {proposal.directions.map((d, n) => {
              const p = previews[n]
              return (
                <div
                  key={n}
                  className={cn(
                    "flex flex-col gap-2 rounded-md border p-3",
                    chosen === n ? "border-music bg-raised" : "border-line bg-ground",
                  )}
                >
                  <p className="font-written text-xl text-ink">{d.title}</p>
                  <p className="text-sm text-ink-2">{d.plain}</p>
                  {p ? (
                    <div className="flex gap-2" role="group" aria-label={`Compare ${d.title} with the song now`}>
                        <Button size="sm" variant={playing?.n === n && playing.side === "new" ? "default" : "outline"} disabled={committing !== null || chosen !== null} onClick={() => play(n, "new")}>

                        {playing?.n === n && playing.side === "new" ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                        New idea
                      </Button>
                      {p.before_url && (
                        <Button size="sm" variant={playing?.n === n && playing.side === "now" ? "default" : "outline"} disabled={committing !== null || chosen !== null} onClick={() => play(n, "now")}>
                          {playing?.n === n && playing.side === "now" ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                          As it is now
                        </Button>
                      )}
                    </div>
                  ) : (
                    <Button size="sm" variant="outline" disabled={loadingPreview !== null || committing !== null} onClick={() => hear(n)}>
                      {loadingPreview === n ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                      Hear it
                    </Button>
                  )}
                  {loadingPreview === n && (
                    <div className="flex items-center gap-2 text-sm text-ink-2" role="status">
                      <span>{previewText}</span>
                      {activeJobId && (
                        <button onClick={() => void stopActive()} className="underline underline-offset-4 hover:text-ink">
                          Stop
                        </button>
                      )}
                    </div>
                  )}
                  {chosen === n ? (
                    <span className="flex items-center gap-1 text-sm text-music">
                      <Check className="h-3.5 w-3.5" /> In the song now
                    </span>
                  ) : (
                    <Button size="sm" variant="outline" disabled={committing !== null || chosen !== null} onClick={() => use(n)}>
                      {committing === n ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                      Use this
                    </Button>
                  )}
                </div>
              )
            })}
          </div>
          {chosen !== null && (
            <p className="text-sm text-ink-2">
              The other ideas were made for the earlier version. Tell me what you hear now, or ask for more ideas.
            </p>
          )}
          {proposal.findings.length > 0 && chosen === null && (
            disagreeing ? (
              <div className="flex gap-2">
                <input
                  value={said}
                  disabled={disagreeing}
                  onChange={(e) => setSaid(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendDisagree()}
                  placeholder="What do you hear instead?"
                  aria-label="What do you hear instead?"
                  className="min-h-11 flex-1 rounded-md bg-raised px-3 py-1.5 text-base text-ink"
                  autoFocus
                />
                <Button size="sm" variant="outline" disabled={disagreeing || !said.trim()} onClick={sendDisagree}>Tell Frank</Button>
              </div>
            ) : (
              <button onClick={() => setDisagreeing(true)} className="self-start text-sm text-ink-2 underline underline-offset-4 hover:text-ink">
                That's not what I'm hearing
              </button>
            )
          )}
        </div>
      )}
    </section>
  )
}
