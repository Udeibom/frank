"use client"

/**
 * Music (the Beat Room): where the music behind the song takes shape.
 *
 * The stage is the arrangement: the song's sections across, the parts down. Every cell can be changed in plain
 * words (busier, simpler, another idea, leave it out), every section can be made fuller or calmer, and every
 * change is a new version listed on the right with what changed. Frank's current question is on the stage;
 * the panel keeps the longer conversation. All sound plays through the shared AudioEngine.
 */

import { useEffect, useRef, useState, useCallback } from "react"
import { useParams, useRouter } from "next/navigation"
import { ConversationPanel, type ChatTurn } from "@/components/conversation/ConversationPanel"
import { FrankNote } from "@/components/conversation/FrankNote"
import { ChangeLine } from "@/components/conversation/ChangeLine"
import { Arrangement, sectionWords } from "@/components/studio/Arrangement"
import { BeatVersions, beatTrack } from "@/components/studio/BeatVersions"
import { RefinePanel } from "@/components/studio/RefinePanel"
import { VersionChoice } from "@/components/studio/VersionChoice"
import { PlayButton } from "@/components/audio/PlayButton"
import { renameVersion } from "@/lib/api/refine"
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
import { accompanyTune, followVoice } from "@/lib/api/organs"
import { pollJob } from "@/lib/api/jobs"
import { useProjectStore } from "@/store/project"
import { useSongStore } from "@/store/song"
import { formatTime, useAudio, usePlayback } from "@/store/audio"
import type { MusicalFingerprint } from "@/types/project"
import type { ConversationMessage, ConversationAction, VersionCandidate } from "@/types/api"

/** What the room is doing right now, in words for the Frank note. */
type Work =
  | { kind: "idle" }
  | { kind: "working"; saying: string; where: { section: number; part?: string } | null }
  | { kind: "failed"; saying: string; retry: () => void }

/** The running order shown while there is no music yet: the shape the music will take. */
const GHOST = ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"]

export default function MusicPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.projectId as string
  const { activeState, updateActiveState, revision } = useProjectStore()
  const record = useSongStore((s) => s.record)

  const greetedRef = useRef(false)
  const [fingerprint, setFingerprint] = useState<Partial<MusicalFingerprint> | null>(null)
  const [versions, setVersions] = useState<BeatVersion[]>([])
  const [activeVersion, setActiveVersion] = useState<BeatVersion | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [isThinking, setIsThinking] = useState(false)
  const [work, setWork] = useState<Work>({ kind: "idle" })
  const [loaded, setLoaded] = useState(false)
  const [stageText, setStageText] = useState("")

  const historyRef = useRef<ConversationMessage[]>([])

  // Refine loop: "something feels wrong" -> directions to hear (spec 08)
  const [refineKey, setRefineKey] = useState(0)
  const [refineConcern, setRefineConcern] = useState<string | null>(null)
  const [candidates, setCandidates] = useState<VersionCandidate[] | null>(null)

  const engine = useAudio()
  const track = activeVersion?.render_url ? beatTrack(activeVersion) : null
  const playback = usePlayback(track?.id)

  const say = useCallback((content: string, actionBlock?: React.ReactNode) => {
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content, actionBlock }])
    if (content) historyRef.current.push({ role: "assistant", content })
  }, [])

  function startRefine(concern: string | null) {
    setRefineConcern(concern)
    setRefineKey((k) => k + 1)
  }

  /** Show a version the server just made active (an edit, a chosen idea) without waiting for the shared state. */
  const adoptVersion = useCallback(
    async (versionId: string) => {
      const vs = await listBeatVersions(projectId)
      setVersions(vs)
      const v = vs.find((x) => x.id === versionId) ?? vs[0] ?? null
      setActiveVersion(v)
      if (v) updateActiveState({ active_beat_version_id: v.id })
      return v
    },
    [projectId, updateActiveState],
  )

  const loadVersions = useCallback(async () => {
    const vs = await listBeatVersions(projectId)
    setVersions(vs)
    const activeId = activeState?.active_beat_version_id
    const active = vs.find((v) => v.id === activeId) ?? vs[0] ?? null
    setActiveVersion(active)
    // Push the newest beat into the shared store so the Voice and Blend rooms know a beat exists and which.
    if (active && active.id !== activeState?.active_beat_version_id) {
      updateActiveState({ active_beat_version_id: active.id })
    }
    return active
  }, [projectId, activeState?.active_beat_version_id, updateActiveState])

  // On entry AND whenever the shared state refreshes: reload the fingerprint and versions so the room reflects
  // anything made elsewhere. Honours the active pointer rather than assuming the newest. Greets only once.
  useEffect(() => {
    Promise.all([getFingerprint(projectId), listBeatVersions(projectId)])
      .then(([fp, vs]) => {
        setFingerprint(fp?.fingerprint ?? null)
        setVersions(vs)
        const active = vs.find((v) => v.id === activeState?.active_beat_version_id) ?? vs[0] ?? null
        setActiveVersion(active)
        setLoaded(true)

        if (greetedRef.current) return
        greetedRef.current = true
        const opening =
          vs.length > 0
            ? "Here's your music. Tell me what you'd like to change, or press any part in the grid."
            : fp?.fingerprint
              ? "Your feeling is ready. Want me to build the music from it? You can also tell me anything specific first."
              : "Let's make the music behind your song. How do you want it to move? Tell me the feeling and I'll build from there."
        setTurns([{ id: crypto.randomUUID(), role: "assistant", content: opening }])
      })
      .catch(() => setLoaded(true))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, revision])

  /** Run a job that makes a new version, saying what is happening on the stage (in place) and in the panel. */
  async function runJob(
    startJob: () => Promise<{ job_id: string }>,
    saying: string,
    where: { section: number; part?: string } | null,
  ) {
    const retry = () => void runJob(startJob, saying, where)
    setWork({ kind: "working", saying, where })
    try {
      const { job_id } = await startJob()
      const done = await pollJob(job_id)
      const madeId = (done.result as { beat_version_id?: string } | null)?.beat_version_id
      const v = madeId ? await adoptVersion(madeId) : await loadVersions()
      const changes = (done.result as { changes?: string[] } | null)?.changes ?? []
      setWork({ kind: "idle" })
      if (v?.render_url) void engine.play(beatTrack(v), { keepPosition: true })
      say(
        "",
        <ChangeLine
          material="music"
          actions={v?.render_url ? [{ label: "Hear it", onClick: () => void engine.play(beatTrack(v), { keepPosition: true }), ariaLabel: `Hear ${v.label}` }] : []}
        >
          {v?.label ?? "New version"}: {changes.length ? changes.join(" ") : "ready"}
        </ChangeLine>,
      )
    } catch (err) {
      // The server's reason is already in plain words ("The drums aren't playing there...").
      const reason = err instanceof Error && err.message ? err.message : "Frank hit a snag making that. Want to try again?"
      setWork({ kind: "failed", saying: reason, retry })
      say(reason)
    }
  }

  function buildMusic() {
    void runJob(() => generateBeat(projectId, fingerprint ?? {}), "Building your music from the feeling. This takes about a minute.", null)
  }

  function change(ops: BeatOperation[], where: { section: number; part?: string }, saying: string) {
    void runJob(() => applyBeatOperations(projectId, ops), saying, where)
  }

  async function dispatchAction(action: ConversationAction) {
    const p = action.params as Record<string, unknown>
    switch (action.type) {
      case "generate_full_beat":
        await runJob(() => generateBeat(projectId, fingerprint ?? {}), "Building your music. This takes about a minute.", null)
        break
      case "beat_operations":
        await runJob(
          () => applyBeatOperations(projectId, (p.operations as BeatOperation[]) ?? []),
          "Working on that. This usually takes a minute or two.",
          null,
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
        await updateSection(projectId, Number(p.section_index), { label: String(p.label) })
        await loadVersions()
        break
    }
  }

  async function handleSend(message: string) {
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "user", content: message }])
    historyRef.current.push({ role: "user", content: message })
    setIsThinking(true)
    try {
      const beatState = {
        sections: activeVersion?.params.sections ?? [],
        versions: versions.map((v) => ({ id: v.id, label: v.label ?? "Beat" })),
      }
      const res = await sendBeatMessage(projectId, message, beatState, historyRef.current.slice(0, -1))
      setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content: res.message }])
      historyRef.current.push({ role: "assistant", content: res.message })
      setIsThinking(false)
      for (const action of res.actions) await dispatchAction(action)
    } catch {
      setIsThinking(false)
      setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content: "Frank zoned out for a second. Say that again?" }])
    }
  }

  async function handleSetActive(versionId: string) {
    await setActiveBeatVersion(projectId, versionId)
    updateActiveState({ active_beat_version_id: versionId })
    const v = versions.find((x) => x.id === versionId) ?? null
    setActiveVersion(v)
    if (v) say("", <ChangeLine material="music">{v.label} is back in the song. Everything after it is kept.</ChangeLine>)
  }

  // "Hear it with my voice": a throwaway preview of the music with the recorded voice over it
  const [previewing, setPreviewing] = useState(false)
  async function handlePreviewWithVocal() {
    setPreviewing(true)
    try {
      const { job_id } = await previewWithVocal(projectId)
      const result = await pollJob(job_id)
      const url = (result.result as { render_url?: string })?.render_url
      if (url) {
        void engine.play({ id: `preview:${url}`, url, label: "The music with your voice", material: "voice", onSong: true })
      }
    } catch {
      say("Couldn't play that back. Make sure you've recorded your voice in the Voice room.")
    } finally {
      setPreviewing(false)
    }
  }

  function playFrom(sectionPosition: number) {
    if (!track) return
    const total = sections.reduce((a, s) => a + s.bars, 0) || 1
    const before = sections.slice(0, sectionPosition).reduce((a, s) => a + s.bars, 0)
    void engine.play(track, { atFraction: before / total })
  }

  const sections: BeatSection[] = activeVersion?.params.sections ?? []
  const hasBeat = Boolean(activeVersion?.render_url)
  const hasVoice = Boolean(record?.vocal)
  const busy = work.kind === "working"
  const lead = describeLead(activeVersion?.params.lead_info)

  // ─── What Frank is saying on the stage ───
  let note: React.ReactNode
  let aside: React.ReactNode
  let answers: { label: string; onClick: () => void; primary?: boolean; disabled?: boolean }[] = []
  if (!loaded) {
    note = "Getting your music ready."
  } else if (work.kind === "working") {
    note = work.saying
    aside = "You can keep working in other rooms while it's made."
  } else if (work.kind === "failed") {
    note = work.saying
    aside = hasBeat ? "The music you had is untouched." : undefined
    answers = [{ label: "Try again", onClick: work.retry }]
  } else if (hasBeat) {
    const follows = Boolean((activeVersion?.params.fingerprint as { follows_voice?: boolean } | undefined)?.follows_voice)
    note = follows
      ? "This music is built around your singing: your speed, chords that fit your notes, and your verses and choruses. Play it, then change anything."
      : "Play it, then change anything. Press a part in a section to make it busier, simpler or leave it out."
    aside = lead ?? undefined
    answers = [
      ...(hasVoice && !follows
        ? [{
            label: "Build the music around my singing",
            primary: true,
            onClick: () => void runJob(() => followVoice(projectId), "Listening to how you sang it, then building the music around you. This takes a minute or two.", null),
          }]
        : []),
      { label: "Something feels off", onClick: () => startRefine(null) },
      ...(hasVoice ? [{ label: previewing ? "Getting your voice…" : "Hear it with my voice", onClick: handlePreviewWithVocal, disabled: previewing }] : []),
      ...(activeVersion?.params.lead_info?.used
        ? [{
            label: "Write a part around my tune",
            onClick: () => void runJob(() => accompanyTune(projectId), "Writing a part to go with your tune. This takes a minute or two.", null),
          }]
        : []),
    ]
  } else if (fingerprint) {
    note = "Your feeling is kept. Ready for Frank to build the music from it?"
    answers = [{ label: "Build the music", onClick: buildMusic, primary: true }]
  } else {
    note = "First, the feeling. Tell me how the song should move, or find it by listening in the Feeling room."
    answers = [{ label: "Go to Feeling", onClick: () => router.push(`/${projectId}/feel`) }]
  }

  const showAsk = loaded && !hasBeat && !fingerprint && work.kind !== "working"

  return (
    <div className="flex h-full">
      <div className="stitch-room room-music flex min-w-0 flex-1 flex-col gap-6 overflow-y-auto px-10 py-8 [--sweep:var(--music)]">
        <div className="flex items-end justify-between gap-4 border-b border-line/60 pb-5">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-music shadow-[0_0_12px_rgb(var(--music)/0.6)]" />
              <h1 className="stitch-title text-ink">Music</h1>
              <span className="stitch-chip">Arrangement Room</span>
            </div>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-on-surface-variant">Shape the sound, energy, and musical parts behind your song.</p>
          </div>
        </div>

        <FrankNote aside={aside} answers={answers} material="music" problem={work.kind === "failed"} busy={busy} appearance="room" roleLabel="Producer Note">
          {note}
        </FrankNote>

        {showAsk && (
          <form
            className="stitch-panel flex flex-col gap-4 p-5"
            onSubmit={(e) => {
              e.preventDefault()
              const text = stageText.trim()
              if (!text || isThinking) return
              setStageText("")
              void handleSend(text)
            }}
          >
            <div className="flex items-center justify-between gap-4">
              <label htmlFor="music-ask" className="text-base font-medium text-on-surface">
                How should it move?
              </label>
              <span className="stitch-kicker text-ink-3">In your own words</span>
            </div>
            <div className="flex items-end gap-3">
              <textarea
                id="music-ask"
                value={stageText}
                onChange={(e) => setStageText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    e.currentTarget.form?.requestSubmit()
                  }
                }}
                rows={2}
                placeholder="Slow and warm, soft piano and gentle drums…"
                className="min-h-[56px] max-w-xl flex-1 resize-none rounded-lg border border-line/60 bg-surface-lowest px-4 py-3 font-written text-[17px] leading-[25px] text-on-surface placeholder:font-sans placeholder:text-base placeholder:text-ink-3"
              />
              <button
                type="submit"
                disabled={!stageText.trim() || isThinking}
                className="stitch-primary h-11 px-5 text-base disabled:bg-surface-high disabled:text-ink-3 disabled:shadow-none"
              >
                {isThinking ? "Listening…" : "Tell Frank"}
              </button>
            </div>
          </form>
        )}

        {refineKey > 0 && (
          <RefinePanel
            projectId={projectId}
            room="beat"
            concern={refineConcern}
            startKey={refineKey}
            onSay={(t) => say(t)}
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
            }}
            onClose={() => setCandidates(null)}
          />
        )}

        <div className="flex min-w-0 flex-col gap-6">
          <section aria-labelledby="arrangement-heading" className="stitch-panel min-w-0 p-5">
            <div className="mb-5 flex items-center gap-4 border-b border-line/50 pb-4">
              {track && <PlayButton track={track} size="stage" />}
              <div className="min-w-0 flex-1">
                <h2 id="arrangement-heading" className="stitch-kicker text-frank-text">
                  The arrangement
                </h2>
                <p className="mt-1 truncate font-written text-xl text-on-surface">
                  {activeVersion?.label ?? "No music yet"}
                  {playback.isCurrent && playback.duration > 0 && (
                    <span className="ml-2 text-sm tabular-nums text-ink-2">
                      {formatTime(playback.position)} / {formatTime(playback.duration)}
                    </span>
                  )}
                </p>
              </div>
              <span className="stitch-chip">{sections.length} sections</span>
            </div>

            {hasBeat ? (
              <Arrangement
                sections={sections}
                progress={playback.isCurrent && playback.duration > 0 ? playback.progress : null}
                busy={busy}
                working={work.kind === "working" ? work.where : null}
                onPlayFrom={playFrom}
                onChange={change}
                onRename={async (idx, label) => {
                  await updateSection(projectId, idx, { label })
                  await loadVersions()
                  say("", <ChangeLine material="music">Renamed a section: {label}</ChangeLine>)
                }}
              />
            ) : (
              <GhostArrangement making={work.kind === "working"} />
            )}
            {hasBeat && (
              <p className="mt-3 text-sm text-ink-2">
                Press a section name to play from there, make it fuller or calmer, or rename it.
                {sections.length > 0 && ` ${sections.length} sections, from ${sectionWords(sections, 0)} to ${sectionWords(sections, sections.length - 1)}.`}
              </p>
            )}
          </section>

          {versions.length > 0 && (
            <div className="stitch-panel max-w-2xl p-5">
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
          )}
        </div>
      </div>

      <ConversationPanel
        projectId={projectId}
        room="beat"
        material="music"
        emptyText="Getting your music ready…"
        turns={turns}
        onSend={handleSend}
        isThinking={isThinking}
        placeholder="Tell Frank what to change…"
      />
    </div>
  )
}

/** The shape the music will take, before there is any: named sections, empty rows, a sweep while it's made. */
function GhostArrangement({ making }: { making: boolean }) {
  return (
    <div aria-hidden="true" className="grid gap-x-1 gap-y-1.5" style={{ gridTemplateColumns: `112px repeat(${GHOST.length}, minmax(80px, 1fr))` }}>
      <div />
      {GHOST.map((g, i) => (
        <span key={`g${i}`} className="px-2 py-1.5 text-sm text-ink-3">
          {g}
        </span>
      ))}
      {["Drums", "Bass", "Keys"].map((part) => (
        <GhostRow key={part} part={part} making={making} />
      ))}
    </div>
  )
}

function GhostRow({ part, making }: { part: string; making: boolean }) {
  return (
    <>
      <span className="flex items-center text-sm text-ink-3">{part}</span>
      {GHOST.map((_, i) => (
        <span key={i} className={making ? "sweep h-9 rounded-[2px]" : "h-9 rounded-[2px] border border-dashed border-ink-3/50"} />
      ))}
    </>
  )
}
