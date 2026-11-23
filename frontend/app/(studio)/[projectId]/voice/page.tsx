"use client"

/**
 * Voice Room — a real vocal session (sing-it spec 06). Sing along with the tune, start from any part with a
 * count-in, practise a part on repeat. Every take is lined up with the beat. Frank can tune it to the song's own
 * notes, line it up, take the music out of it, build the best version line by line, add a harmony that follows
 * the chords, or turn what you sang into the song's tune. The original of every take is always kept.
 */

import { recordingName } from "@/lib/recordingName"
import { useEffect, useRef, useState, useCallback, useMemo } from "react"
import { useParams, useRouter } from "next/navigation"
import { ConversationPanel, type ChatTurn } from "@/components/conversation/ConversationPanel"
import { VocalRecorder, type SongSection } from "@/components/audio/VocalRecorder"
import { DelayCheck } from "@/components/audio/DelayCheck"
import { HeadphoneCheck, headphonesChecked } from "@/components/audio/HeadphoneCheck"
import { quietTake, sungGuide, takeAsInstrument } from "@/lib/api/organs"
import { TakeCard, type TakeAction } from "@/components/studio/TakeCard"
import { CompView } from "@/components/studio/CompView"
import { FrankNote } from "@/components/conversation/FrankNote"
import { PlayButton } from "@/components/audio/PlayButton"
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
import { useSongStore } from "@/store/song"
import { useAudio } from "@/store/audio"
import type { ConversationMessage, ConversationAction } from "@/types/api"
import { Timer } from "lucide-react"

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
  const router = useRouter()
  const projectId = params.projectId as string
  const { activeState, updateActiveState, revision, refresh } = useProjectStore()
  const record = useSongStore((s) => s.record)
  const engine = useAudio()

  const [takes, setTakes] = useState<VocalTake[]>([])
  const [beat, setBeat] = useState<BeatVersion | null>(null)
  const [guide, setGuide] = useState<{ url: string | null; note: string | null; beatId: string | null }>({ url: null, note: null, beatId: null })
  const [delayKnown, setDelayKnown] = useState<boolean | null>(null)
  const [showDelayCheck, setShowDelayCheck] = useState(false)
  const [showHeadphoneCheck, setShowHeadphoneCheck] = useState(false)
  const [wearingHeadphones, setWearingHeadphones] = useState<boolean | null>(null)
  const [sungGuideUrl, setSungGuideUrl] = useState<string | null>(null)
  const play = useAudio((st) => st.play)
  const [comp, setComp] = useState<ActiveComp | null>(null)
  const [heard, setHeard] = useState<HeardTune | null>(null)
  const [uploading, setUploading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [picked, setPicked] = useState<string[]>([])
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [isThinking, setIsThinking] = useState(false)
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
          "Whenever you're ready, record yourself. Pick where to start, and I'll count you in. Want to hear the tune while you sing? Turn on \"Sing along with the tune\". Sing it as many times as you like: I keep every one.",
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

  async function wantSungGuide() {
    if (!beat) return
    await runJob(() => sungGuide(projectId), "A guide voice is learning your words. This takes a minute or two…", "Here's how the line could go.", (r) => {
      if (typeof r.guide_url === "string") {
        setSungGuideUrl(r.guide_url)
        void play({ id: `sung-guide:${beat.id}`, url: r.guide_url, label: "The guide singing your words", material: "voice" })
      }
    })
  }

  async function handleRecorded(blob: Blob, ext: string, placement: TakePlacement | null, headphones: boolean | null) {
    setUploading(true)
    try {
      const { take, analysis_job_id } = await uploadTake(projectId, blob, ext, placement, headphones)
      setTakes((t) => [take, ...t])
      updateActiveState({ active_vocal_id: take.id, active_comp_id: null })
      pollJob(analysis_job_id)
        .then(async (done) => {
          const r = done.result as { engineer?: string | null; music_job_id?: string } | null
          if (r?.engineer) say(r.engineer)                     // the recording engineer: at most one thing
          await refreshTakes()
          if (r?.music_job_id) {
            // Frank builds the music around how they sang it, without being asked (core-path spec 15, requirement 8)
            say("Now I'm building the music around how you sang it: your speed, chords that fit your notes, and your verses and choruses. This takes a minute or two…")
            try {
              const built = await pollJob(r.music_job_id)
              const msg = (built.result as { message?: string } | null)?.message
              if (msg) say(msg)
              await refresh(projectId)
            } catch (err) {
              if (err instanceof Error && err.message) say(err.message)
            }
          }
        })
        .catch(() => {})
    } catch {
      say("Something went wrong saving that recording. Want to try again?")
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
      case "quiet":
        return runJob(() => quietTake(projectId, take.id), "Taking the room noise out of your recording…", "Done. Your original is kept, so you can compare.")
      case "instrument":
        return runJob(
          () => takeAsInstrument(projectId, take.id, action.instrument),
          "Playing what you sang on an instrument. This one takes a minute or two…",
          "Here it is, played the way you sang it. Your original is kept.",
        )
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
  const words = record?.lyrics?.trim() ?? ""
  const inSong = takes.find((t) => t.id === (activeState?.active_vocal_id ?? ""))
  const canBlend = picked.length >= 2 || roots.length >= 2

  // ─── What Frank is saying on the stage ───
  let note: React.ReactNode
  let answers: { label: string; onClick: () => void; primary?: boolean; disabled?: boolean }[] = []
  if (heard) {
    note = heard.description || "Here's the tune I heard in what you sang. Is that your tune?"
    answers = [
      {
        label: "Hear it",
        onClick: () => void engine.toggle({ id: `tune:${heard.version_id}`, url: heard.preview_url, label: "The tune I heard", material: "voice" }),
      },
      {
        label: "Yes, that's my tune",
        primary: true,
        onClick: async () => {
          await confirmTune(projectId, heard.version_id)
          setHeard(null)
          say("That's the song's tune now. Next time the music is built or changed, it will follow it.")
        },
      },
      {
        label: "Not quite",
        onClick: async () => {
          await rejectTune(projectId, heard.version_id)
          setHeard(null)
          say("No problem, I've set it aside. Sing it again whenever you like.")
        },
      },
    ]
  } else if (busy) {
    note = "Working on your voice. Your original recording is always kept."
  } else if (!beat) {
    note = "There's no music yet. You can record just your voice now, or build the music first and sing along with it."
    answers = [{ label: "Build the music", onClick: () => router.push(`/${projectId}/beat`) }]
  } else if (roots.length === 0) {
    note = "Pick where to start and press Record. I'll count you in. Sing it as many times as you like: I keep every recording."
  } else {
    note = `${recordingName(inSong?.label, "A recording")} is in the song. Record again any time; every recording is kept.`
    if (canBlend) {
      answers = [
        {
          label: picked.length >= 2 ? `Best of ${picked.length} recordings` : "Best of all my recordings",
          onClick: () => void blend(picked.length >= 2 ? picked : roots.map((t) => t.id)),
        },
      ]
    }
  }

  return (
    <div className="flex h-full">
      <div className="room-voice flex min-w-0 flex-1 flex-col gap-7 overflow-y-auto px-10 py-8 [--sweep:var(--voice)]">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span aria-hidden="true" className="h-3 w-3 rounded-full bg-voice" />
            <h1 className="font-written italic text-3xl" style={{ color: "rgb(var(--voice))" }}>Voice</h1>
            <span className="text-sm text-ink-3">Record your voice</span>
          </div>
          <div className="flex items-center gap-4">
          {!showHeadphoneCheck && (
            <button onClick={() => setShowHeadphoneCheck(true)} className="text-sm text-ink-2 hover:text-ink">
              Check my headphones
            </button>
          )}
          {beat && words && (
            <button onClick={() => void wantSungGuide()} disabled={busy} className="text-sm text-ink-2 hover:text-ink disabled:text-ink-3">
              {sungGuideUrl ? "Hear the guide sing it again" : "Hear it sung with my words"}
            </button>
          )}
          {delayKnown && !showDelayCheck && (
            <button onClick={() => setShowDelayCheck(true)} className="flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink">
              <Timer className="h-4 w-4" aria-hidden="true" /> Check the timing again
            </button>
          )}
          </div>
        </div>

        {showHeadphoneCheck && (
          <HeadphoneCheck
            onResult={(wearing) => setWearingHeadphones(wearing)}
            onClose={() => setShowHeadphoneCheck(false)}
          />
        )}

        <FrankNote answers={answers} material="voice" busy={busy}>
          {note}
        </FrankNote>

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

        {/* The booth: your words in front of you, the recorder beside them */}
        <div className="flex min-w-0 gap-10">
          <section aria-labelledby="your-words" className="min-w-0 max-w-[520px] flex-1">
            <h2 id="your-words" className="mb-3 text-xs font-semibold uppercase tracking-[0.06em] text-ink-3">
              Your words
            </h2>
            {words ? (
              <div className="max-h-[440px] overflow-y-auto rounded-md bg-surface p-5">
                <p className="whitespace-pre-wrap font-written text-xl leading-[1.6] text-ink">{words}</p>
              </div>
            ) : (
              <div className="rounded-md border border-dashed border-ink-3/60 p-5">
                <p className="text-base text-ink-2">
                  No words yet. Sing whatever you have, or write them first in{" "}
                  <button onClick={() => router.push(`/${projectId}/idea`)} className="text-ink underline underline-offset-4 hover:text-frank">
                    Words
                  </button>
                  .
                </p>
              </div>
            )}
          </section>
          <section aria-label="Record" className="flex w-[360px] shrink-0 flex-col items-center rounded-md bg-surface p-6">
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
              initialHeadphones={wearingHeadphones ?? headphonesChecked()}
            />
          </section>
        </div>

        {/* Takes */}
        <section aria-labelledby="takes-heading" className="flex max-w-[920px] flex-col gap-3">
          <h2 id="takes-heading" className="text-xs font-semibold uppercase tracking-[0.06em] text-ink-3">
            {roots.length ? `Your recordings (${roots.length})` : "Your recordings"}
          </h2>
          {comp && (
            <CompView
              comp={comp}
              takes={takes}
              busy={busy}
              inUse={activeState?.active_comp_id === comp.id}
              onUse={useComp}
              onSwap={swap}
            />
          )}
          {roots.length === 0 ? (
            <div aria-hidden="true" className="flex h-24 items-center rounded-md border border-dashed border-ink-3/60 px-5">
              <span className="text-base text-ink-3">Each recording you make appears here, with how steady it was.</span>
            </div>
          ) : (
            roots.map((take) => (
              <TakeCard
                key={take.id}
                projectId={projectId}
                take={take}
                versions={children[take.id] ?? []}
                activeId={activeTakeId}
                busy={busy}
                picked={picked.includes(take.id)}
                canUseAsMelody={!hasOwnTune}
                recordings={roots.length}
                onUse={chooseActive}
                onPick={(id) => setPicked((sel) => (sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]))}
                onAction={act}
              />
            ))
          )}
          {harmonies.length > 0 && (
            <div className="mt-3 flex flex-col gap-2">
              <h2 className="text-xs font-semibold uppercase tracking-[0.06em] text-ink-3">Second voices (Blend turns them on or off)</h2>
              {harmonies.map((h) => (
                <div key={h.id} className="flex items-center gap-3 rounded-md bg-surface px-3 py-2">
                  <PlayButton track={{ id: `take:${h.id}`, url: h.audio_url, label: h.label ?? "Second voice", material: "voice" }} size="row" />
                  <span className="text-base text-ink">{h.label}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <ConversationPanel
        projectId={projectId}
        room="voice"
        material="voice"
        emptyText="Getting your recordings ready…"
        turns={turns}
        onSend={handleSend}
        isThinking={isThinking}
        placeholder="Ask about your singing…"
      />
    </div>
  )
}
