"use client"

/**
 * Beat Room — where the music behind the song takes shape.
 * Build the beat from the feeling, then shape it section by section and layer
 * by layer through conversation. Every change is a new version; nothing is lost.
 */

import { useEffect, useRef, useState, useCallback } from "react"
import { useParams } from "next/navigation"
import {
  ConversationPanel,
  type ChatTurn,
} from "@/components/conversation/ConversationPanel"
import { BeatTimeline } from "@/components/studio/BeatTimeline"
import { BeatVersions } from "@/components/studio/BeatVersions"
import { RefinePanel } from "@/components/studio/RefinePanel"
import { VersionChoice } from "@/components/studio/VersionChoice"
import { renameVersion } from "@/lib/api/refine"
import { Button } from "@/components/ui/button"
import {
  generateBeat,
  sendBeatMessage,
  listBeatVersions,
  setActiveBeatVersion,
  updateSection,
  previewWithVocal,
  describeLead,
  applyBeatOperations,
  type BeatOperation,
  type BeatVersion,
  type BeatSection,
} from "@/lib/api/beat"
import { getFingerprint } from "@/lib/api/feel"
import { pollJob } from "@/lib/api/jobs"
import { useProjectStore } from "@/store/project"
import type { MusicalFingerprint } from "@/types/project"
import type { ConversationMessage, ConversationAction, VersionCandidate } from "@/types/api"
import { Drum, Play, Pause, Loader2, Mic2, Ear } from "lucide-react"

export default function BeatRoomPage() {
  const params = useParams()
  const projectId = params.projectId as string
  const { activeState, updateActiveState, revision } = useProjectStore()

  const greetedRef = useRef(false)
  const [fingerprint, setFingerprint] = useState<Partial<MusicalFingerprint> | null>(null)
  const [versions, setVersions] = useState<BeatVersion[]>([])
  const [activeVersion, setActiveVersion] = useState<BeatVersion | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [isThinking, setIsThinking] = useState(false)
  const [building, setBuilding] = useState(false)

  // Playback of the active beat
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)

  const historyRef = useRef<ConversationMessage[]>([])

  // Refine loop: "something feels wrong" -> directions to hear (spec 08)
  const [refineKey, setRefineKey] = useState(0)
  const [refineConcern, setRefineConcern] = useState<string | null>(null)
  const [candidates, setCandidates] = useState<VersionCandidate[] | null>(null)

  const say = useCallback((content: string) => {
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content }])
    historyRef.current.push({ role: "assistant", content })
  }, [])

  function startRefine(concern: string | null) {
    setRefineConcern(concern)
    setRefineKey((k) => k + 1)
  }

  /** Show a version the server just made active (an edit, a chosen idea) without waiting for the shared state. */
  const adoptVersion = useCallback(async (versionId: string) => {
    const vs = await listBeatVersions(projectId)
    setVersions(vs)
    const v = vs.find((x) => x.id === versionId) ?? vs[0] ?? null
    setActiveVersion(v)
    if (v) updateActiveState({ active_beat_version_id: v.id })
  }, [projectId, updateActiveState])

  const loadVersions = useCallback(async () => {
    const vs = await listBeatVersions(projectId)
    setVersions(vs)
    const activeId = activeState?.active_beat_version_id
    const active = vs.find((v) => v.id === activeId) ?? vs[0] ?? null
    setActiveVersion(active)
    // Push the newest beat into the shared store so the Voice and Mix Rooms
    // immediately know a beat exists and which one is current.
    if (active && active.id !== activeState?.active_beat_version_id) {
      updateActiveState({ active_beat_version_id: active.id })
    }
    return active
  }, [projectId, activeState?.active_beat_version_id, updateActiveState])

  // On entry AND whenever the shared state refreshes: reload the fingerprint
  // and beats so the room reflects anything made elsewhere (e.g. the feel the
  // user just approved). Honors the active beat pointer rather than assuming
  // the newest. Greets only once.
  useEffect(() => {
    Promise.all([getFingerprint(projectId), listBeatVersions(projectId)]).then(
      ([fp, vs]) => {
        setFingerprint(fp?.fingerprint ?? null)
        setVersions(vs)
        const active =
          vs.find((v) => v.id === activeState?.active_beat_version_id) ?? vs[0] ?? null
        setActiveVersion(active)

        if (greetedRef.current) return
        greetedRef.current = true

        if (vs.length > 0) {
          setTurns([
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content:
                "Here's your beat. Tell me what you'd like to change — make a part fuller, bring the energy up, strip something back. Whatever you're hearing.",
            },
          ])
        } else if (fp?.fingerprint) {
          setTurns([
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content:
                "Your feel is ready. Want me to build the beat from it? You can also tell me anything specific first.",
            },
          ])
        } else {
          setTurns([
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content:
                "Let's make the music behind your song. First — how do you want it to move? Tell me the feeling and I'll build from there.",
            },
          ])
        }
      },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, revision])

  // Set up audio element when the active beat changes
  useEffect(() => {
    audioRef.current?.pause()
    setPlaying(false)
    setProgress(0)
    if (!activeVersion?.render_url) {
      audioRef.current = null
      return
    }
    const audio = new Audio(activeVersion.render_url)
    audio.addEventListener("timeupdate", () => {
      if (audio.duration) setProgress(audio.currentTime / audio.duration)
    })
    audio.addEventListener("ended", () => {
      setPlaying(false)
      setProgress(0)
    })
    audioRef.current = audio
    return () => {
      audio.pause()
    }
  }, [activeVersion?.render_url])

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

  function seek(fraction: number) {
    const audio = audioRef.current
    if (!audio || !audio.duration) return
    audio.currentTime = fraction * audio.duration
    setProgress(fraction)
  }

  async function runJobWithStatus(
    startJob: () => Promise<{ job_id: string }>,
    pendingMessage: string,
  ) {
    const placeholderId = crypto.randomUUID()
    setTurns((t) => [
      ...t,
      { id: placeholderId, role: "assistant", content: pendingMessage },
    ])
    setBuilding(true)
    const say = (content: string) =>
      setTurns((t) => t.map((turn) => (turn.id === placeholderId ? { ...turn, content } : turn)))
    try {
      const { job_id } = await startJob()
      const done = await pollJob(job_id)
      const madeId = (done.result as { beat_version_id?: string } | null)?.beat_version_id
      if (madeId) await adoptVersion(madeId)
      else await loadVersions()
      const changes = (done.result as { changes?: string[] } | null)?.changes ?? []
      say(
        changes.length
          ? `${changes.join(" ")} Have a listen. How does that feel?`
          : "Done. Have a listen and tell me how it feels.",
      )
    } catch (err) {
      // The server's reason is already in plain words ("The drums aren't playing there...").
      say(err instanceof Error && err.message ? err.message : "Frank hit a snag making that. Want to try again?")
    } finally {
      setBuilding(false)
    }
  }

  async function handleBuildBeat() {
    await runJobWithStatus(
      () => generateBeat(projectId, fingerprint ?? {}),
      "Building your beat… this takes a minute.",
    )
  }

  async function dispatchAction(action: ConversationAction) {
    const p = action.params as Record<string, unknown>
    switch (action.type) {
      case "generate_full_beat":
        await runJobWithStatus(
          () => generateBeat(projectId, fingerprint ?? {}),
          "Building your beat… this takes a minute.",
        )
        break
      case "beat_operations":
        await runJobWithStatus(
          () => applyBeatOperations(projectId, (p.operations as BeatOperation[]) ?? []),
          "Working on that… this usually takes a minute or two.",
        )
        break
      case "restore_version":
        await handleSetActive(String(p.version_id))
        break
      case "refine":
        startRefine(typeof p.concern === "string" ? p.concern : null)
        break
      case "compare_versions":
        setCandidates((p.candidates as VersionCandidate[]) ?? [])
        break
      case "set_section_label":
        await updateSection(projectId, Number(p.section_index), {
          label: String(p.label),
        })
        await loadVersions()
        break
    }
  }

  async function handleSend(message: string) {
    setTurns((t) => [
      ...t,
      { id: crypto.randomUUID(), role: "user", content: message },
    ])
    historyRef.current.push({ role: "user", content: message })
    setIsThinking(true)

    try {
      const beatState = {
        sections: activeVersion?.params.sections ?? [],
        versions: versions.map((v) => ({ id: v.id, label: v.label ?? "Beat" })),
      }
      const res = await sendBeatMessage(
        projectId,
        message,
        beatState,
        historyRef.current.slice(0, -1),
      )
      setTurns((t) => [
        ...t,
        { id: crypto.randomUUID(), role: "assistant", content: res.message },
      ])
      historyRef.current.push({ role: "assistant", content: res.message })
      setIsThinking(false)

      // Execute any actions sequentially
      for (const action of res.actions) {
        await dispatchAction(action)
      }
    } catch {
      setIsThinking(false)
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Frank zoned out for a second — say that again?",
        },
      ])
    }
  }

  async function handleSetActive(versionId: string) {
    await setActiveBeatVersion(projectId, versionId)
    updateActiveState({ active_beat_version_id: versionId })
    const v = versions.find((x) => x.id === versionId) ?? null
    setActiveVersion(v)
  }

  // "Hear it with my vocal" — a throwaway preview of beat + the recorded vocal
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const previewAudioRef = useRef<HTMLAudioElement | null>(null)
  const [previewing, setPreviewing] = useState(false)

  async function handlePreviewWithVocal() {
    setPreviewing(true)
    setTurns((t) => [
      ...t,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "Let me play the beat with your voice over it…",
      },
    ])
    try {
      const { job_id } = await previewWithVocal(projectId)
      const result = await pollJob(job_id)
      const url = (result.result as { render_url?: string })?.render_url
      if (url) {
        setPreviewUrl(url)
        previewAudioRef.current?.pause()
        const audio = new Audio(url)
        previewAudioRef.current = audio
        audio.play().catch(() => {})
      }
    } catch {
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            "Couldn't play that back — make sure you've recorded a vocal in the Voice Room.",
        },
      ])
    } finally {
      setPreviewing(false)
    }
  }

  const sections: BeatSection[] = activeVersion?.params.sections ?? []
  const hasBeat = Boolean(activeVersion?.render_url)

  return (
    <div className="flex h-screen">
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-8 py-3">
          <div>
            <h1 className="text-sm font-semibold text-foreground">Beat Room</h1>
            <p className="text-xs text-muted-foreground">
              Shape the music behind your song
            </p>
          </div>
          {!hasBeat && fingerprint && (
            <Button onClick={handleBuildBeat} disabled={building}>
              {building ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Drum className="h-4 w-4" />
              )}
              Build the beat
            </Button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-8 py-6">
          {hasBeat ? (
            <div className="flex flex-col gap-6">
              {/* Transport */}
              <div className="flex items-center gap-4">
                <button
                  onClick={togglePlay}
                  className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground transition-transform hover:scale-105"
                  aria-label={playing ? "Pause" : "Play"}
                >
                  {playing ? (
                    <Pause className="h-5 w-5" />
                  ) : (
                    <Play className="h-5 w-5 translate-x-0.5" />
                  )}
                </button>
                <div className="flex-1 text-sm text-muted-foreground">
                  {activeVersion?.label}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={previewing || building}
                  onClick={handlePreviewWithVocal}
                >
                  {previewing ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Mic2 className="h-3.5 w-3.5" />
                  )}
                  Hear it with my vocal
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={building}
                  onClick={() => startRefine(null)}
                >
                  <Ear className="h-3.5 w-3.5" />
                  Something feels off
                </Button>
              </div>

              {describeLead(activeVersion?.params.lead_info) && (
                <p className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-2 text-sm text-foreground">
                  {describeLead(activeVersion?.params.lead_info)}
                </p>
              )}

              {refineKey > 0 && (
                <RefinePanel
                  projectId={projectId}
                  room="beat"
                  concern={refineConcern}
                  startKey={refineKey}
                  onSay={say}
                  onCommitted={async (result) => {
                    const id = result?.beat_version_id
                    if (typeof id === "string") await adoptVersion(id)
                    else await loadVersions()
                  }}
                  onClose={() => setRefineKey(0)}
                />
              )}

              {candidates && (
                <VersionChoice
                  candidates={candidates}
                  onPick={async (id) => {
                    setCandidates(null)
                    await handleSetActive(id)
                    say("That one's back on. Everything after it is still kept.")
                  }}
                  onClose={() => setCandidates(null)}
                />
              )}

              {/* Timeline */}
              <BeatTimeline
                sections={sections}
                progress={progress}
                onSeek={seek}
                onRenameSection={async (idx, label) => {
                  await updateSection(projectId, idx, { label })
                  await loadVersions()
                }}
              />

              {/* Versions */}
              <BeatVersions
                versions={versions}
                activeVersionId={activeVersion?.id ?? null}
                onSetActive={handleSetActive}
                onRename={async (id, label) => {
                  await renameVersion(projectId, "beat", id, label)
                  setVersions((vs) => vs.map((v) => (v.id === id ? { ...v, label } : v)))
                }}
              />
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="rounded-full bg-primary/10 p-6">
                <Drum className="h-10 w-10 text-primary" />
              </div>
              <p className="mt-6 max-w-sm text-sm text-muted-foreground leading-relaxed">
                {fingerprint
                  ? "Press Build the beat, or just tell Frank what you're going for on the right."
                  : "Tell Frank how the song should move, over on the right, and the beat will start to come together."}
              </p>
            </div>
          )}
        </div>
      </div>

      <ConversationPanel
        projectId={projectId}
        room="beat"
        emptyText="Getting your beat ready…"
        turns={turns}
        onSend={handleSend}
        isThinking={isThinking}
        placeholder="Tell Frank what to change…"
      />
    </div>
  )
}
