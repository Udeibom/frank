"use client"

/**
 * Voice Room — a real vocal session (sing-it spec 06). Sing along with the tune, start from any part with a
 * count-in, practise a part on repeat. Every take is lined up with the beat. Frank can tune it to the song's own
 * notes, line it up, take the music out of it, build the best version line by line, add a harmony that follows
 * the chords, or turn what you sang into the song's tune. The original of every take is always kept.
 */

import { useEffect, useRef, useState, useCallback, useMemo } from "react"
import { useParams } from "next/navigation"
import { ConversationPanel, type ChatTurn } from "@/components/conversation/ConversationPanel"
import { VocalRecorder, type SongSection } from "@/components/audio/VocalRecorder"
import { DelayCheck } from "@/components/audio/DelayCheck"
import { TakeCard, type TakeAction } from "@/components/studio/TakeCard"
import { CompView } from "@/components/studio/CompView"
import { Button } from "@/components/ui/button"
import {
  uploadTake,
  listTakes,
  correctPitch,
  lineUp,
  removeBleed,
  takeAsMelody,
  makeGuide,
  buildComp,
  getActiveComp,
  swapPhrase,
  generateHarmony,
  setActiveVocal,
  getVoiceSettings,
  sendVoiceMessage,
  type ActiveComp,
  type TakePlacement,
  type VocalTake,
} from "@/lib/api/voice"
import { listBeatVersions, type BeatVersion } from "@/lib/api/beat"
import { confirmTune, rejectTune } from "@/lib/api/intake"
import { pollJob } from "@/lib/api/jobs"
import { useProjectStore } from "@/store/project"
import type { ConversationMessage, ConversationAction } from "@/types/api"
import { Play, Pause, Wand2, Timer } from "lucide-react"

type Job = { job_id: string }

interface HeardTune {
  version_id: string
  preview_url: string
  description: string
}

function sectionsOf(beat: BeatVersion | null): { sections: SongSection[]; spb: number } {
  const bpm = Number((beat?.params as { fingerprint?: { tempo_bpm?: number } } | undefined)?.fingerprint?.tempo_bpm ?? 90) || 90
  const spb = 60 / bpm
  const out: SongSection[] = []
  let at = 0
  for (const s of beat?.params.sections ?? []) {
    const len = s.bars * 4 * spb
    out.push({ index: s.index, label: s.label || s.name, start: at, end: at + len })
    at += len
  }
  // "Chorus", "Chorus" -> "Chorus 1", "Chorus 2", so the picker is clear
  const seen: Record<string, number> = {}
  for (const s of out) {
    const base = s.label
    const n = (beat?.params.sections ?? []).filter((x) => (x.label || x.name) === base).length
    if (n > 1) {
      seen[base] = (seen[base] ?? 0) + 1
      s.label = `${base} ${seen[base]}`
    }
  }
  return { sections: out, spb }
}

export default function VoiceRoomPage() {
  const params = useParams()
  const projectId = params.projectId as string
  const { activeState, updateActiveState, revision } = useProjectStore()

  const [takes, setTakes] = useState<VocalTake[]>([])
  const [beat, setBeat] = useState<BeatVersion | null>(null)
  const [guide, setGuide] = useState<{ url: string | null; note: string | null; beatId: string | null }>({ url: null, note: null, beatId: null })
  const [delayKnown, setDelayKnown] = useState<boolean | null>(null)
  const [showDelayCheck, setShowDelayCheck] = useState(false)
  const [comp, setComp] = useState<ActiveComp | null>(null)
  const [heard, setHeard] = useState<HeardTune | null>(null)
  const [uploading, setUploading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [picked, setPicked] = useState<string[]>([])
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [isThinking, setIsThinking] = useState(false)
  const [playingUrl, setPlayingUrl] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const historyRef = useRef<ConversationMessage[]>([])

  const say = useCallback((content: string) => {
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content }])
    historyRef.current.push({ role: "assistant", content })
  }, [])

  const refreshTakes = useCallback(async () => {
    const t = await listTakes(projectId)
    setTakes(t)
    return t
  }, [projectId])

  const refreshComp = useCallback(async () => {
    const { comp } = await getActiveComp(projectId)
    setComp(comp)
  }, [projectId])

  useEffect(() => {
    setTurns([
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          "Whenever you're ready, record your take. Pick where to start, and I'll count you in. Want to hear the tune while you sing? Turn on \"Sing along with the tune\". Sing it as many times as you like: I keep every one.",
      },
    ])
    getVoiceSettings(projectId)
      .then((s) => {
        setDelayKnown(s.input_delay_ms !== null)
        setShowDelayCheck(s.input_delay_ms === null)
      })
      .catch(() => setDelayKnown(null))
  }, [projectId])

  useEffect(() => {
    refreshTakes()
    refreshComp().catch(() => {})
    listBeatVersions(projectId).then((vs) => {
      const active = vs.find((v) => v.id === activeState?.active_beat_version_id) ?? vs[0] ?? null
      setBeat(active)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, revision])

  const { sections, spb } = useMemo(() => sectionsOf(beat), [beat])
  const hasOwnTune = Boolean((beat?.params as { lead_info?: { used?: boolean } } | undefined)?.lead_info?.used)

  // Group: each recorded take with the versions made from it; harmonies on their own.
  const { roots, children, harmonies } = useMemo(() => {
    const byId = new Map(takes.map((t) => [t.id, t]))
    const rootOf = (t: VocalTake): string => {
      let cur = t
      for (let i = 0; i < 10 && cur.parent_take_id && byId.has(cur.parent_take_id) && !cur.is_harmony; i++) cur = byId.get(cur.parent_take_id)!
      return cur.id
    }
    const roots = takes.filter((t) => !t.is_harmony && (!t.parent_take_id || !byId.has(t.parent_take_id)))
    const children: Record<string, VocalTake[]> = {}
    for (const t of takes) {
      if (t.is_harmony || roots.includes(t)) continue
      ;(children[rootOf(t)] ??= []).push(t)
    }
    for (const k of Object.keys(children)) children[k].sort((a, b) => a.created_at.localeCompare(b.created_at))
    return { roots, children, harmonies: takes.filter((t) => t.is_harmony) }
  }, [takes])

  function playUrl(url: string) {
    if (playingUrl === url) {
      audioRef.current?.pause()
      setPlayingUrl(null)
      return
    }
    audioRef.current?.pause()
    const audio = new Audio(url)
    audio.onended = () => setPlayingUrl(null)
    audio.play().then(() => {
      audioRef.current = audio
      setPlayingUrl(url)
    }).catch(() => setPlayingUrl(null))
  }

  async function wantGuide() {
    if (!beat) return
    if (guide.beatId === beat.id && (guide.url || guide.note)) return
    try {
      const { job_id } = await makeGuide(projectId)
      const done = await pollJob(job_id)
      const r = done.result as { guide_url?: string | null; message?: string }
      setGuide({ url: r.guide_url ?? null, note: r.message ?? null, beatId: beat.id })
      if (r.message) say(r.message)
    } catch (err) {
      setGuide({ url: null, note: err instanceof Error ? err.message : null, beatId: beat.id })
    }
  }

  async function handleRecorded(blob: Blob, ext: string, placement: TakePlacement | null, headphones: boolean | null) {
    setUploading(true)
    try {
      const { take, analysis_job_id } = await uploadTake(projectId, blob, ext, placement, headphones)
      setTakes((t) => [take, ...t])
      updateActiveState({ active_vocal_id: take.id, active_comp_id: null })
      pollJob(analysis_job_id)
        .then((done) => {
          const engineer = (done.result as { engineer?: string | null } | null)?.engineer
          if (engineer) say(engineer)                          // the recording engineer: at most one thing
          return refreshTakes()
        })
        .catch(() => {})
    } catch {
      say("Something went wrong saving that take. Want to try again?")
    } finally {
      setUploading(false)
    }
  }

  /** Run a voice job, say what Frank did in its own words, and show the new version. */
  async function runJob(start: () => Promise<Job>, pending: string, fallback: string, after?: (result: Record<string, unknown>) => Promise<void> | void) {
    setBusy(true)
    const id = crypto.randomUUID()
    setTurns((t) => [...t, { id, role: "assistant", content: pending }])
    const set = (content: string) => setTurns((t) => t.map((x) => (x.id === id ? { ...x, content } : x)))
    try {
      const { job_id } = await start()
      const done = await pollJob(job_id)
      const result = (done.result ?? {}) as Record<string, unknown>
      set(typeof result.message === "string" && result.message ? result.message : fallback)
      await refreshTakes()
      if (after) await after(result)
    } catch (err) {
      set(err instanceof Error && err.message ? err.message : "Frank hit a snag there. Want to try again?")
    } finally {
      setBusy(false)
    }
  }

  async function act(take: VocalTake, action: TakeAction) {
    switch (action.kind) {
      case "tune":
        return runJob(() => correctPitch(projectId, take.id, action.mode), "Tuning it to the notes of your song…", "Done. Compare it with your original.")
      case "line_up":
        return runJob(() => lineUp(projectId, take.id), "Lining your lines up with the beat…", "Done. Your original is kept.")
      case "remove_bleed":
        return runJob(() => removeBleed(projectId, take.id), "Taking the music out of your vocal…", "Done. Have a listen with and without.")
      case "harmony":
        return runJob(() => generateHarmony(projectId, take.id, action.type, action.sections), "Building a harmony from your voice…", "Your harmony is ready.")
      case "use_as_melody":
        return runJob(() => takeAsMelody(projectId, take.id), "Listening for the tune in what you sang…", "Here's what I heard.", (r) => {
          if (r.ok && typeof r.version_id === "string") {
            setHeard({ version_id: r.version_id, preview_url: String(r.preview_url), description: String(r.description ?? "") })
          } else if (typeof r.reason === "string") {
            say(r.reason)
          }
        })
    }
  }

  async function chooseActive(take: VocalTake) {
    await setActiveVocal(projectId, take.id, "take")
    updateActiveState({ active_vocal_id: take.id, active_comp_id: null })
  }

  async function useComp() {
    if (!comp) return
    await setActiveVocal(projectId, comp.id, "comp")
    updateActiveState({ active_comp_id: comp.id })
    setComp({ ...comp, active: true })
  }

  async function blend(ids: string[]) {
    await runJob(() => buildComp(projectId, ids), "Putting together the best version, line by line…", "Here's the best-of version.", async (r) => {
      if (typeof r.comp_id === "string") updateActiveState({ active_comp_id: r.comp_id })
      await refreshComp()
    })
  }

  async function swap(phraseIndex: number, takeId: string) {
    if (!comp) return
    await runJob(() => swapPhrase(projectId, comp.id, phraseIndex, takeId), "Swapping that line…", "Swapped.", async (r) => {
      if (typeof r.comp_id === "string") updateActiveState({ active_comp_id: r.comp_id })
      await refreshComp()
    })
  }

  async function dispatchAction(action: ConversationAction) {
    const p = action.params as Record<string, unknown>
    const take = takes.find((t) => t.id === (typeof p.take_id === "string" ? p.take_id : activeState?.active_vocal_id)) ?? roots[0]
    switch (action.type) {
      case "correct_pitch":
        if (take) await act(take, { kind: "tune", mode: (p.mode as "light" | "moderate" | "full") ?? "light" })
        break
      case "line_up":
        if (take) await act(take, { kind: "line_up" })
        break
      case "remove_bleed":
        if (take) await act(take, { kind: "remove_bleed" })
        break
      case "add_harmony":
        if (take) await act(take, { kind: "harmony", type: (p.type as "above" | "below" | "both") ?? "above", sections: (p.sections as string[]) ?? null })
        break
      case "use_as_melody":
        if (take) await act(take, { kind: "use_as_melody" })
        break
      case "build_comp":
        if (roots.length >= 2) await blend(roots.map((t) => t.id))
        break
      case "guide":
        if (p.on !== false) await wantGuide()
        break
    }
  }

  async function handleSend(message: string) {
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "user", content: message }])
    historyRef.current.push({ role: "user", content: message })
    setIsThinking(true)
    try {
      const res = await sendVoiceMessage(projectId, message, historyRef.current.slice(0, -1))
      setIsThinking(false)
      say(res.message)
      for (const action of res.actions) await dispatchAction(action)
    } catch {
      setIsThinking(false)
      say("Frank stepped away for a second. Say that again?")
    }
  }

  const activeTakeId = activeState?.active_comp_id ? null : activeState?.active_vocal_id ?? null

  return (
    <div className="flex h-screen">
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-8 py-3">
          <div>
            <h1 className="text-sm font-semibold text-foreground">Voice Room</h1>
            <p className="text-xs text-muted-foreground">Record your voice</p>
          </div>
          {delayKnown && !showDelayCheck && (
            <button onClick={() => setShowDelayCheck(true)} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              <Timer className="h-3.5 w-3.5" /> Redo the timing check
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-8 py-8">
          {showDelayCheck && beat && (
            <DelayCheck
              projectId={projectId}
              onDone={(m) => {
                say(m)
                setDelayKnown(true)
                setShowDelayCheck(false)
              }}
              onClose={() => setShowDelayCheck(false)}
            />
          )}

          <div className="mb-10">
            <VocalRecorder
              beatUrl={beat?.render_url ?? null}
              beatVersionId={beat?.id ?? null}
              sections={sections}
              secondsPerBeat={spb}
              guideUrl={guide.beatId === beat?.id ? guide.url : null}
              guideNote={guide.beatId === beat?.id ? guide.note : null}
              onWantGuide={wantGuide}
              uploading={uploading}
              onRecorded={handleRecorded}
            />
          </div>

          {heard && (
            <section aria-label="The tune I heard" className="mx-auto mb-6 max-w-2xl rounded-xl border border-primary/30 bg-card p-4">
              <p className="mb-2 text-sm text-foreground">{heard.description || "Here's the tune I heard in what you sang."}</p>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => playUrl(heard.preview_url)}>
                  {playingUrl === heard.preview_url ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />} Hear it
                </Button>
                <Button size="sm" onClick={async () => {
                  await confirmTune(projectId, heard.version_id)
                  setHeard(null)
                  say("That's the song's tune now. Next time the beat is built or changed, it will follow it.")
                }}>
                  Yes, that&apos;s my tune
                </Button>
                <Button size="sm" variant="outline" onClick={async () => {
                  await rejectTune(projectId, heard.version_id)
                  setHeard(null)
                  say("No problem, I've set it aside. Sing it again whenever you like.")
                }}>
                  Not quite
                </Button>
              </div>
            </section>
          )}

          {(roots.length > 0 || comp) && (
            <div className="mx-auto max-w-2xl">
              {comp && (
                <CompView comp={comp} takes={takes} busy={busy} playingUrl={playingUrl} inUse={activeState?.active_comp_id === comp.id}
                          onPlay={playUrl} onUse={useComp} onSwap={swap} />
              )}
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-medium text-muted-foreground">Your takes ({roots.length})</h2>
                {picked.length >= 2 ? (
                  <Button size="sm" disabled={busy} onClick={() => blend(picked)}>
                    <Wand2 className="h-3.5 w-3.5" /> Best of {picked.length} takes
                  </Button>
                ) : roots.length >= 2 ? (
                  <Button size="sm" variant="outline" disabled={busy} onClick={() => blend(roots.map((t) => t.id))}>
                    <Wand2 className="h-3.5 w-3.5" /> Best of all my takes
                  </Button>
                ) : null}
              </div>
              <div className="flex flex-col gap-3">
                {roots.map((take) => (
                  <TakeCard
                    key={take.id}
                    take={take}
                    versions={children[take.id] ?? []}
                    activeId={activeTakeId}
                    playingUrl={playingUrl}
                    busy={busy}
                    picked={picked.includes(take.id)}
                    canUseAsMelody={!hasOwnTune}
                    onPlay={playUrl}
                    onUse={chooseActive}
                    onPick={(id) => setPicked((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]))}
                    onAction={act}
                  />
                ))}
              </div>
              {harmonies.length > 0 && (
                <div className="mt-6">
                  <h2 className="mb-2 text-sm font-medium text-muted-foreground">Harmonies (the Mix Room turns them on or off)</h2>
                  {harmonies.map((h) => (
                    <div key={h.id} className="mb-2 flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2">
                      <button onClick={() => playUrl(h.audio_url)} aria-label={playingUrl === h.audio_url ? "Pause harmony" : "Play harmony"}
                              className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-primary hover:bg-primary/25">
                        {playingUrl === h.audio_url ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5 translate-x-px" />}
                      </button>
                      <span className="text-sm text-foreground">{h.label}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <ConversationPanel
        projectId={projectId}
        room="voice"
        emptyText="Getting your takes ready…"
        turns={turns}
        onSend={handleSend}
        isThinking={isThinking}
        placeholder="Ask Frank for help with your voice…"
      />
    </div>
  )
}
