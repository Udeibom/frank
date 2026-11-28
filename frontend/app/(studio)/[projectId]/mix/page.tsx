"use client"

/**
 * Mix Room — where the voice, the beat, and any harmony come together into one
 * song. The user shapes the balance entirely by listening and talking. Every
 * adjustment renders a new mix; nothing is overwritten.
 */

import { useEffect, useRef, useState, useCallback, type CSSProperties } from "react"
import { useParams, useRouter } from "next/navigation"
import {
  ConversationPanel,
  type ChatTurn,
} from "@/components/conversation/ConversationPanel"
import { StemBalance } from "@/components/studio/StemBalance"
import { AtmospherePanel, ConductPanel, ListenPanel } from "@/components/studio/BlendOrgans"
import { MixVersions, mixTrack, summarize } from "@/components/studio/MixVersions"
import { FrankNote } from "@/components/conversation/FrankNote"
import { PlayButton } from "@/components/audio/PlayButton"
import { RefinePanel } from "@/components/studio/RefinePanel"
import { VersionChoice } from "@/components/studio/VersionChoice"
import { renameVersion } from "@/lib/api/refine"
import { getParts, PART_NAMES, type SongParts } from "@/lib/api/finish"
import {
  renderMix,
  sendMixMessage,
  listMixVersions,
  setActiveMixVersion,
  type MixVersion,
  type MixParams,
} from "@/lib/api/mix"
import { listTakes } from "@/lib/api/voice"
import { listBeatVersions } from "@/lib/api/beat"
import { pollJob } from "@/lib/api/jobs"
import { useProjectStore } from "@/store/project"
import type { ConversationAction, ConversationMessage, VersionCandidate } from "@/types/api"

const DEFAULT_PARAMS: Partial<MixParams> = {
  vocal_gain_db: 0,
  beat_gain_db: -6,
  harmony_gain_db: -4,
  harmony_enabled: true,
  vocal_effects: [],
  beat_effects: [],
  section_gain_db: {},
}

const WAVE_BARS = [18, 26, 34, 22, 42, 58, 48, 30, 24, 52, 68, 46, 36, 60, 74, 54, 38, 28, 44, 64, 82, 58, 42, 30, 48, 72, 56, 40, 26, 34, 22, 16]

export default function MixRoomPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.projectId as string
  const { activeState, updateActiveState, revision } = useProjectStore()

  const [hasVocal, setHasVocal] = useState(false)
  const [hasBeat, setHasBeat] = useState(false)
  const [hasHarmony, setHasHarmony] = useState(false)
  const [versions, setVersions] = useState<MixVersion[]>([])
  const [activeVersion, setActiveVersion] = useState<MixVersion | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [isThinking, setIsThinking] = useState(false)
  const [rendering, setRendering] = useState(false)
  const [failed, setFailed] = useState(false)

  const mixParamsRef = useRef<Partial<MixParams>>({ ...DEFAULT_PARAMS })
  const historyRef = useRef<ConversationMessage[]>([])
  // Guards so we greet once and auto-assemble the first mix only once.
  const greetedRef = useRef(false)
  const autoAssembledRef = useRef(false)

  // Refine loop (spec 08)
  const [refineKey, setRefineKey] = useState(0)
  const [refineConcern, setRefineConcern] = useState<string | null>(null)
  const [candidates, setCandidates] = useState<VersionCandidate[] | null>(null)
  const [songParts, setSongParts] = useState<SongParts | null>(null)
  const [partTick, setPartTick] = useState(0)        // re-draw after a part change (params live in a ref)

  useEffect(() => {
    getParts(projectId).then(setSongParts).catch(() => setSongParts(null))
  }, [projectId, revision])

  /** "Keys a bit softer", "Drums off": one part of the music, then a new mix (spec 11, requirement 1). */
  async function changePart(part: string, change: { level_delta_db?: number; muted?: boolean }) {
    const current = mixParamsRef.current.parts ?? {}
    const st = { ...(current[part] ?? {}) }
    if (change.level_delta_db) st.level_db = Math.max(-24, Math.min(12, (st.level_db ?? 0) + change.level_delta_db))
    if (change.muted !== undefined) st.muted = change.muted
    mixParamsRef.current = { ...mixParamsRef.current, parts: { ...current, [part]: st } }
    setPartTick((x) => x + 1)
    const name = PART_NAMES[part] ?? part
    say(
      songParts?.ready
        ? `${name} ${change.muted === true ? "off" : change.muted === false ? "back on" : change.level_delta_db! > 0 ? "a bit louder" : "a bit softer"}. Mixing it now…`
        : "First I'll separate the music into its parts. That happens once and takes a few minutes; after that each change is quick.",
    )
    await doRender(mixParamsRef.current)
    if (!songParts?.ready) getParts(projectId).then(setSongParts).catch(() => {})
  }

  const say = useCallback((content: string) => {
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content }])
    historyRef.current.push({ role: "assistant", content })
  }, [])

  function startRefine(concern: string | null) {
    setRefineConcern(concern)
    setRefineKey((k) => k + 1)
  }

  // Arriving from the Export Room with "Not yet": start listening with the person's own words.
  useEffect(() => {
    const concern = new URLSearchParams(window.location.search).get("refine")
    if (concern !== null) {
      startRefine(concern || null)
      window.history.replaceState(null, "", window.location.pathname)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /** Show the mix the server just made active, without waiting for the shared state to catch up. */
  const adoptMix = useCallback(async (mixId: string) => {
    const vs = await listMixVersions(projectId)
    setVersions(vs)
    const v = vs.find((x) => x.id === mixId) ?? vs[0] ?? null
    setActiveVersion(v)
    if (v?.mix_params) mixParamsRef.current = { ...DEFAULT_PARAMS, ...v.mix_params }
    if (v) updateActiveState({ active_mix_id: v.id })
  }, [projectId, updateActiveState])

  const loadVersions = useCallback(async () => {
    const vs = await listMixVersions(projectId)
    setVersions(vs)
    const active = vs.find((v) => v.id === activeState?.active_mix_id) ?? vs[0] ?? null
    setActiveVersion(active)
    if (active?.mix_params) {
      mixParamsRef.current = { ...DEFAULT_PARAMS, ...active.mix_params }
    }
    return active
  }, [projectId, activeState?.active_mix_id])

  // On entry AND whenever the shared state refreshes (navigating in from the
  // Voice/Beat rooms), re-check what exists and reload mixes. This is what lets
  // the Mix Room always see the vocal and beat you just made elsewhere.
  useEffect(() => {
    Promise.all([
      listTakes(projectId),
      listBeatVersions(projectId),
      listMixVersions(projectId),
    ]).then(([takes, beats, mixes]) => {
      const vocalTakes = takes.filter(
        (t) => !(t.is_harmony || (t.label ?? "").toLowerCase().startsWith("harmony")),
      )
      const harmonies = takes.filter((t) =>
        t.is_harmony || (t.label ?? "").toLowerCase().startsWith("harmony"),
      )
      const haveVocal = vocalTakes.length > 0
      const haveBeat = beats.length > 0
      setHasVocal(haveVocal)
      setHasBeat(haveBeat)
      setHasHarmony(harmonies.length > 0)
      setVersions(mixes)
      const active =
        mixes.find((m) => m.id === activeState?.active_mix_id) ?? mixes[0] ?? null
      setActiveVersion(active)
      if (active?.mix_params) {
        mixParamsRef.current = { ...DEFAULT_PARAMS, ...active.mix_params }
      }

      // Greet once (don't reset the conversation on every re-sync).
      if (!greetedRef.current) {
        greetedRef.current = true
        if (mixes.length > 0) {
          setTurns([
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content:
                "Here's how it sounds right now. Tell me what you'd change — is the voice sitting right? Too much music? Something feel off? I'll adjust and we'll listen again.",
            },
          ])
        } else if (haveVocal && haveBeat) {
          setTurns([
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content: "Let me put your voice and the music together. One moment…",
            },
          ])
        } else {
          const missing = !haveVocal ? "your voice" : "music"
          setTurns([
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content: `We need ${missing} before we can blend the song. It's waiting in ${!haveVocal ? "the Voice room" : "the Music room"}; I'll be ready when you are.`,
            },
          ])
        }
      }

      // Auto-assemble the first mix once, when both parts exist and none yet.
      if (mixes.length === 0 && haveVocal && haveBeat && !autoAssembledRef.current) {
        autoAssembledRef.current = true
        doRender(mixParamsRef.current)
      }
    }).catch(() => {
      // Never leave the room silently empty if a request fails.
      setTurns([
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            "I couldn't reach your song just now. Give it a moment and refresh. Nothing has been lost.",
        },
      ])
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, revision])

  async function doRender(mixParams: Partial<MixParams>, quality: "preview" | "full" = "preview") {
    setRendering(true)
    setFailed(false)
    try {
      const { job_id } = await renderMix(projectId, mixParams, quality)
      const done = await pollJob(job_id)
      const madeId = (done.result as { mix_version_id?: string } | null)?.mix_version_id
      if (madeId) await adoptMix(madeId)
      else await loadVersions()
    } catch {
      setFailed(true)
      say("Frank couldn't put the blend together just then. Want to try again?")
    } finally {
      setRendering(false)
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
      const res = await sendMixMessage(
        projectId,
        message,
        mixParamsRef.current,
        historyRef.current.slice(0, -1),
      )
      mixParamsRef.current = res.mix_params
      setTurns((t) => [
        ...t,
        { id: crypto.randomUUID(), role: "assistant", content: res.message },
      ])
      historyRef.current.push({ role: "assistant", content: res.message })
      setIsThinking(false)
      for (const action of res.actions as ConversationAction[]) {
        const ap = action.params as Record<string, unknown>
        if (action.type === "refine") startRefine(typeof ap.concern === "string" ? ap.concern : null)
        if (action.type === "compare_versions") setCandidates((ap.candidates as VersionCandidate[]) ?? [])
        if (action.type === "restore_mix_version") await handleSetActive(String(ap.version_id))
      }
      if (res.render) await doRender(res.mix_params)
    } catch {
      setIsThinking(false)
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Frank lost the thread for a second — say that again?",
        },
      ])
    }
  }

  async function handleToggleHarmony(on: boolean) {
    mixParamsRef.current = { ...mixParamsRef.current, harmony_enabled: on }
    await doRender(mixParamsRef.current)
  }

  async function handleSetActive(versionId: string) {
    await setActiveMixVersion(projectId, versionId)
    updateActiveState({ active_mix_id: versionId })
    const v = versions.find((x) => x.id === versionId) ?? null
    setActiveVersion(v)
    if (v?.mix_params) mixParamsRef.current = { ...DEFAULT_PARAMS, ...v.mix_params }
  }

  const hasMix = Boolean(activeVersion?.render_url)
  const track = activeVersion?.render_url ? mixTrack(activeVersion) : null
  // The blend before this one: what "compare" switches to, at the same moment.
  const activeIndex = versions.findIndex((v) => v.id === activeVersion?.id)
  const previous = activeIndex >= 0 ? versions.slice(activeIndex + 1).find((v) => v.render_url) ?? null : null

  // ─── What Frank is saying on the stage ───
  let note: React.ReactNode
  let aside: React.ReactNode
  let answers: { label: string; onClick: () => void; primary?: boolean; disabled?: boolean }[] = []
  if (rendering) {
    note = "Putting the blend together. This usually takes under a minute."
    aside = "The blend you had stays as it is until the new one is ready."
  } else if (failed) {
    note = "Frank couldn't put the blend together just then."
    aside = hasMix ? "The blend you had is untouched." : "Your voice and music are safe."
    answers = [{ label: "Try again", onClick: () => void doRender(mixParamsRef.current) }]
  } else if (!hasVocal || !hasBeat) {
    // Blocked: say what is missing and offer the way there, instead of a play button that can't play.
    note = !hasVocal ? "To blend the song, it needs your voice first." : "To blend the song, it needs music first."
    answers = [
      !hasVocal
        ? { label: "Record your voice", onClick: () => router.push(`/${projectId}/voice`), primary: true }
        : { label: "Build the music", onClick: () => router.push(`/${projectId}/beat`), primary: true },
    ]
  } else if (hasMix) {
    note = "This is your voice and the music together. Listen, then tell Frank what you'd change, like \"my voice is too quiet\" or \"too much going on\". When it sounds right, finish it."
    answers = [
      { label: "It sounds right: finish it", onClick: () => router.push(`/${projectId}/export`), primary: true },
      { label: "Something feels off", onClick: () => startRefine(null) },
    ]
  } else {
    note = "Putting your voice and the music together for the first time."
  }

  return (
    <div className="flex h-full">
      <div className="stitch-room flex min-w-0 flex-1 flex-col gap-6 overflow-y-auto px-4 py-6 sm:px-6 md:px-10 md:py-8 [--sweep:var(--voice)]">
        <div className="flex flex-col gap-4 border-b border-line/60 pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-frank shadow-[0_0_12px_rgb(var(--frank)/0.6)]" />
              <h1 className="stitch-title text-ink">Blend</h1>
              <span className="stitch-chip">Room 05</span>
            </div>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-on-surface-variant">Bring your voice and the music together.</p>
          </div>
        </div>

        <FrankNote aside={aside} answers={answers} problem={failed} busy={rendering} appearance="room" roleLabel="Producer Note">
          {note}
        </FrankNote>

        {(hasMix || rendering) && (
          <section aria-labelledby="listen-heading" className="stitch-panel flex flex-col gap-4 p-4 sm:p-5">
            <div className="flex flex-wrap items-center gap-4 sm:gap-5">
              {track ? <PlayButton track={track} size="stage" keepPosition /> : <span className="sweep h-12 w-12 rounded-full" aria-hidden="true" />}
              <div className="min-w-0 flex-1">
                <h2 id="listen-heading" className="stitch-kicker text-frank-text">The song right now</h2>
                <p className="mt-1 truncate font-written text-xl text-on-surface">
                  {activeVersion?.label ?? "The first blend"}
                  {activeVersion && <span className="ml-2 text-sm font-sans text-ink-2">{summarize(activeVersion)}</span>}
                </p>
              </div>
              {previous && track && (
                <div role="group" aria-label="Compare with the blend before" className="flex flex-wrap items-center gap-3 border-line pl-0 sm:border-l sm:pl-5">
                  <span className="text-sm text-ink-2">Compare with before</span>
                  <PlayButton track={mixTrack(previous)} size="card" keepPosition />
                </div>
              )}
            </div>
            <div className="rounded-xl border border-line/50 bg-surface-lowest px-4 py-3">
              <div className="stitch-waveform">
                {WAVE_BARS.map((height, i) => (
                  <span key={i} style={{ "--bar-height": `${height}%` } as CSSProperties} />
                ))}
              </div>
            </div>
          </section>
        )}

        {refineKey > 0 && (
          <RefinePanel
            projectId={projectId}
            room="mix"
            concern={refineConcern}
            startKey={refineKey}
            onSay={say}
            onCommitted={async (result) => {
              const id = result?.mix_version_id
              if (typeof id === "string") await adoptMix(id)
              else if (result?.beat_version_id) await doRender(mixParamsRef.current) // the music changed: hear it in the blend
              else await loadVersions()
            }}
            onClose={() => setRefineKey(0)}
          />
        )}

        {candidates && (
          <VersionChoice
            candidates={candidates}
            material="voice"
            onPick={async (id) => {
              setCandidates(null)
              await handleSetActive(id)
              say("That blend is back on. Everything after it is still kept.")
            }}
            onClose={() => setCandidates(null)}
          />
        )}

        {hasMix && (
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="stitch-kicker text-frank-text">Listening bays</h2>
            <span className="text-sm text-ink-2">Every change is saved, so you can always go back.</span>
          </div>
        )}
        {hasMix && (
          <div className="grid max-w-[1000px] gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <ListenPanel projectId={projectId} onFix={(concern) => startRefine(concern)} />
            <AtmospherePanel
              projectId={projectId}
              current={(activeVersion?.mix_params as { atmosphere?: { enabled?: boolean; plain?: string } } | undefined)?.atmosphere ?? null}
              onDone={() => void loadVersions()}
            />
            {songParts?.parts && songParts.parts.length > 0 && (
              <ConductPanel parts={songParts.parts} onSet={(part, d) => void changePart(part, { level_delta_db: d })} />
            )}
          </div>
        )}

        <div className="grid w-full max-w-[1000px] gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          {(hasVocal || hasBeat) && (
            <div className="stitch-panel p-4 sm:p-5">
              <StemBalance
                hasVocal={hasVocal}
                hasBeat={hasBeat}
                hasHarmony={hasHarmony}
                harmonyEnabled={mixParamsRef.current.harmony_enabled ?? true}
                onToggleHarmony={handleToggleHarmony}
                parts={songParts?.parts}
                partSettings={partTick >= 0 ? mixParamsRef.current.parts : undefined}
                busy={rendering}
                onPart={hasVocal && hasBeat ? changePart : undefined}
              />
            </div>
          )}
          <div className="stitch-panel p-5">
            <MixVersions
              versions={versions}
              activeVersionId={activeVersion?.id ?? null}
              onSetActive={handleSetActive}
              onRename={async (id, label) => {
                await renameVersion(projectId, "mix", id, label)
                setVersions((vs) => vs.map((v) => (v.id === id ? { ...v, label } : v)))
              }}
            />
          </div>
        </div>
      </div>

      <ConversationPanel
        projectId={projectId}
        room="mix"
        material="voice"
        emptyText="Getting your blend ready…"
        turns={turns}
        onSend={handleSend}
        isThinking={isThinking}
        placeholder="Tell Frank what to change…"
      />
    </div>
  )
}
