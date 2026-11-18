"use client"

/**
 * RefinePanel — "something feels wrong" (spec 08). Frank listens, says what it heard, and offers two or three
 * directions. Each can be heard before choosing, and compared with the song as it is now at the same moment.
 * "Use this" makes it a new version; the earlier one is kept.
 */

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { askForDirections, chooseDirection, disagree, previewDirection } from "@/lib/api/refine"
import { pollJob } from "@/lib/api/jobs"
import type { RefinePreview, RefineProposal } from "@/types/api"
import { Ear, Loader2, Play, Pause, Check, X } from "lucide-react"
import { cn } from "@/lib/utils"

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
  const [playing, setPlaying] = useState<{ n: number; side: Side } | null>(null)
  const [disagreeing, setDisagreeing] = useState(false)
  const [said, setSaid] = useState("")
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    if (startKey <= 0) return
    let cancelled = false
    setPhase("listening")
    setProgress("Listening to your song… this takes about a minute.")
    setProposal(null)
    setPreviews({})
    setChosen(null)
    askForDirections(projectId, concern, room, (t) => !cancelled && setProgress(t))
      .then((p) => {
        if (cancelled) return
        setProposal(p)
        setPhase("ready")
        onSay(p.message)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setPhase("error")
        setProgress(err instanceof Error ? err.message : "I couldn't listen just now. Want to try again?")
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startKey])

  useEffect(() => () => audioRef.current?.pause(), [])

  function stop() {
    audioRef.current?.pause()
    setPlaying(null)
  }

  /** Play one side; switching sides keeps the same moment, so the difference is easy to hear. */
  function play(n: number, side: Side) {
    const p = previews[n]
    const url = side === "new" ? p?.preview_url : p?.before_url
    if (!url) return
    if (playing?.n === n && playing.side === side) {
      stop()
      return
    }
    const at = playing?.n === n ? audioRef.current?.currentTime ?? 0 : 0
    audioRef.current?.pause()
    const audio = new Audio(url)
    audio.onended = () => setPlaying(null)
    audio.addEventListener("loadedmetadata", () => {
      audio.currentTime = Math.min(at, Math.max(0, audio.duration - 0.1))
    })
    audioRef.current = audio
    audio.play().then(() => setPlaying({ n, side })).catch(() => setPlaying(null))
  }

  async function hear(n: number) {
    if (!proposal) return
    if (previews[n]) {
      play(n, "new")
      return
    }
    setLoadingPreview(n)
    setPreviewText("Playing it the new way… usually under a minute.")
    try {
      const p = await previewDirection(projectId, proposal.proposal_id, n, setPreviewText)
      setPreviews((all) => ({ ...all, [n]: p }))
      const audio = new Audio(p.preview_url)
      audio.onended = () => setPlaying(null)
      audioRef.current?.pause()
      audioRef.current = audio
      audio.play().then(() => setPlaying({ n, side: "new" })).catch(() => {})
    } catch (err) {
      onSay(err instanceof Error ? err.message : "I couldn't play that idea just now. Want to try again?")
    } finally {
      setLoadingPreview(null)
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
    if (!proposal || !said.trim()) return
    const res = await disagree(projectId, proposal.proposal_id, said.trim())
    onSay(res.message)
    setSaid("")
    setDisagreeing(false)
  }

  return (
    <section aria-label="Ideas to try" className="rounded-xl border border-primary/30 bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Ear className="h-4 w-4 text-primary" />
          {proposal?.experiment ? "Let your ears decide" : "A few ways to go"}
        </div>
        <button onClick={onClose} aria-label="Close ideas" className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>

      {phase !== "ready" && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          {phase === "listening" && <Loader2 className="h-4 w-4 animate-spin" />}
          {progress}
        </p>
      )}

      {phase === "ready" && proposal && (
        <div className="flex flex-col gap-3">
          {proposal.findings.length > 0 && (
            <ul className="list-disc pl-5 text-xs text-muted-foreground">
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
                    "flex flex-col gap-2 rounded-lg border p-3",
                    chosen === n ? "border-primary bg-primary/10" : "border-border bg-background",
                  )}
                >
                  <p className="text-sm font-medium text-foreground">{d.title}</p>
                  <p className="text-xs text-muted-foreground">{d.plain}</p>
                  {p ? (
                    <div className="flex gap-2" role="group" aria-label={`Compare ${d.title} with the song now`}>
                      <Button size="sm" variant={playing?.n === n && playing.side === "new" ? "default" : "outline"} onClick={() => play(n, "new")}>
                        {playing?.n === n && playing.side === "new" ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                        New idea
                      </Button>
                      {p.before_url && (
                        <Button size="sm" variant={playing?.n === n && playing.side === "now" ? "default" : "outline"} onClick={() => play(n, "now")}>
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
                  {loadingPreview === n && <p className="text-[11px] text-muted-foreground" role="status">{previewText}</p>}
                  {chosen === n ? (
                    <span className="flex items-center gap-1 text-xs text-primary">
                      <Check className="h-3.5 w-3.5" /> In the song now
                    </span>
                  ) : (
                    <Button size="sm" disabled={committing !== null || chosen !== null} onClick={() => use(n)}>
                      {committing === n ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                      Use this
                    </Button>
                  )}
                </div>
              )
            })}
          </div>
          {chosen !== null && (
            <p className="text-xs text-muted-foreground">
              The other ideas were made for the earlier version. Tell me what you hear now, or ask for more ideas.
            </p>
          )}
          {proposal.findings.length > 0 && chosen === null && (
            disagreeing ? (
              <div className="flex gap-2">
                <input
                  value={said}
                  onChange={(e) => setSaid(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendDisagree()}
                  placeholder="What do you hear instead?"
                  aria-label="What do you hear instead?"
                  className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm"
                  autoFocus
                />
                <Button size="sm" variant="outline" onClick={sendDisagree}>Tell Frank</Button>
              </div>
            ) : (
              <button onClick={() => setDisagreeing(true)} className="self-start text-xs text-muted-foreground underline hover:text-foreground">
                That's not what I'm hearing
              </button>
            )
          )}
        </div>
      )}
    </section>
  )
}
