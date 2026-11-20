"use client"

/**
 * Feeling (the Feel Lab): where the song finds its feeling.
 *
 * The stage is a listening bench: every direction Frank has played is a card you can hear, switch between in
 * time, keep or set aside. Hum and tap are controls on the stage. Frank's current question is a note on the
 * stage with its answers as buttons; the conversation panel keeps the longer talk.
 * The musical fingerprint is still built quietly as the conversation goes; it is never shown.
 */

import { useEffect, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { ConversationPanel, type ChatTurn } from "@/components/conversation/ConversationPanel"
import { ChangeLine } from "@/components/conversation/ChangeLine"
import { FrankNote } from "@/components/conversation/FrankNote"
import { DirectionCard, directionTrack } from "@/components/studio/DirectionCard"
import { HumIntake } from "@/components/studio/HumIntake"
import { RhythmIntake } from "@/components/studio/RhythmIntake"
import { sendFeelMessage, generateTexture, saveFingerprint, getFingerprint, getTextureWaveform } from "@/lib/api/feel"
import { pollJob } from "@/lib/api/jobs"
import { useProjectStore } from "@/store/project"
import { useSongStore } from "@/store/song"
import { useDirections, type Direction } from "@/store/directions"
import { useAudio } from "@/store/audio"
import { plainSound } from "@/lib/feelWords"
import type { MusicalFingerprint } from "@/types/project"
import type { ConversationMessage } from "@/types/api"

const GREETING =
  "Let's find the feeling of your song. Don't worry about music words, just tell me how it should feel. Where does it take you?"

export default function FeelingPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.projectId as string
  const { updateActiveState, refresh } = useProjectStore()
  const record = useSongStore((s) => s.record)
  const loadSong = useSongStore((s) => s.load)

  const directions = useDirections((s) => s.directions)
  const directionsLoaded = useDirections((s) => s.loaded)
  const { startMaking, finishMaking, failMaking, setAside, setWaveform, remove } = useDirections.getState()
  const playing = useAudio((s) => s.playing)
  const currentTrackId = useAudio((s) => s.track?.id)
  const play = useAudio((s) => s.play)

  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [isThinking, setIsThinking] = useState(false)
  // The direction Frank thinks the person has landed on (he said "approve_direction").
  const [suggestedId, setSuggestedId] = useState<string | null>(null)
  // The direction just kept in this visit, before the shared song record has caught up.
  const [keptHere, setKeptHere] = useState<string | null>(null)
  const [lastWords, setLastWords] = useState<string | null>(null)
  const [stageText, setStageText] = useState("")

  // The evolving fingerprint and conversation history (read at send time)
  const fingerprintRef = useRef<Partial<MusicalFingerprint>>({})
  const historyRef = useRef<ConversationMessage[]>([])
  const summaryRef = useRef<string>("")
  const lastTextureIdRef = useRef<string | null>(null)

  const keptId = keptHere ?? ((record?.fingerprint as { reference_texture_id?: string } | null)?.reference_texture_id ?? null)
  const making = directions.some((d) => d.status === "making")
  const ready = directions.filter((d) => d.status === "ready")

  // Opening: load any existing fingerprint (return visit) or greet fresh.
  useEffect(() => {
    void useDirections.getState().load(projectId)
    getFingerprint(projectId)
      .then((existing) => {
        if (existing && existing.fingerprint) {
          fingerprintRef.current = existing.fingerprint
          summaryRef.current = existing.conversation_summary ?? ""
          const recap = existing.conversation_summary
            ? ` Last time we landed on something like: "${existing.conversation_summary}".`
            : ""
          setTurns([
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content: `Welcome back.${recap} Want to keep going from here, or try something different?`,
            },
          ])
        } else {
          setTurns([{ id: crypto.randomUUID(), role: "assistant", content: GREETING }])
        }
      })
      .catch(() => {
        setTurns([{ id: crypto.randomUUID(), role: "assistant", content: GREETING }])
      })
  }, [projectId])

  function say(content: string, actionBlock?: React.ReactNode) {
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content, actionBlock }])
    // Frank's next reply must know what Frank just said (for example that the tune was confirmed).
    if (content) historyRef.current.push({ role: "assistant", content })
  }

  // Merge a fingerprint update, concatenating list fields rather than replacing.
  function mergeFingerprint(update: Partial<MusicalFingerprint>) {
    const prev = fingerprintRef.current
    const merged: Partial<MusicalFingerprint> = { ...prev, ...update }
    // Preserve accumulated list hints instead of clobbering them
    for (const key of ["genre_proximity", "instrumentation_hints"] as const) {
      const prevList = (prev[key] as string[] | undefined) ?? []
      const nextList = (update[key] as string[] | undefined) ?? []
      if (prevList.length || nextList.length) {
        merged[key] = Array.from(new Set([...prevList, ...nextList]))
      }
    }
    fingerprintRef.current = merged
  }

  async function runTextureGeneration() {
    const tempId = startMaking()
    // What this direction is, in plain words, from what Frank knew when he made it.
    const note = plainSound(fingerprintRef.current) || undefined
    try {
      const { job_id } = await generateTexture(projectId, fingerprintRef.current)
      const result = await pollJob(job_id)
      const payload = result.result as { audio_url?: string; texture_id?: string; waveform?: number[] } | null
      if (!payload?.audio_url || !payload.texture_id) throw new Error("no sound came back")
      const id = payload.texture_id
      lastTextureIdRef.current = id
      finishMaking(tempId, { id, url: payload.audio_url, waveform: payload.waveform ?? null, note })
      if (!payload.waveform) {
        getTextureWaveform(projectId, id)
          .then((points) => setWaveform(id, points))
          .catch(() => setWaveform(id, []))
      }
      const made = useDirections.getState().directions.find((d) => d.id === id)
      if (made) {
        // Arrives playing, in time with whatever was playing before.
        void play(directionTrack(made), { keepPosition: true })
        // Frank's own sentence just before this already said what it is; this line is the record of the change.
        say(
          "",
          <ChangeLine material="feel" actions={[{ label: "Hear it", onClick: () => void play(directionTrack(made), { keepPosition: true }), ariaLabel: `Hear Direction ${made.number}` }]}>
            Direction {made.number} is ready
          </ChangeLine>,
        )
      }
    } catch {
      failMaking(tempId)
      say("I couldn't find that sound just now. Want me to try again?")
    }
  }

  async function handleSend(message: string) {
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "user", content: message }])
    historyRef.current.push({ role: "user", content: message })
    setLastWords(message)
    setIsThinking(true)

    try {
      const res = await sendFeelMessage(projectId, message, fingerprintRef.current, historyRef.current.slice(0, -1))

      // Merge the fingerprint update (list fields accumulate, not clobber)
      mergeFingerprint(res.fingerprint_update)

      setTurns((t) => [...t, { id: crypto.randomUUID(), role: "assistant", content: res.message }])
      historyRef.current.push({ role: "assistant", content: res.message })
      summaryRef.current = res.message

      // Act on the two possible Feeling actions
      const wantsTexture = res.actions.some((a) => a.type === "generate_texture")
      const approved = res.actions.some((a) => a.type === "approve_direction")
      if (approved) setSuggestedId(lastTextureIdRef.current)

      if (wantsTexture) {
        setIsThinking(false)
        await runTextureGeneration()
        return
      }
    } catch {
      setTurns((t) => [
        ...t,
        { id: crypto.randomUUID(), role: "assistant", content: "I lost the connection for a moment. Could you send that again?" },
      ])
    } finally {
      setIsThinking(false)
    }
  }

  function sayAsFrank(content: string) {
    say(content)
  }

  function handleTuneConfirmed(info: { hints: Partial<MusicalFingerprint>; description: string; unsureAbout: string[] }) {
    // The song now has a tune: let the rest of the studio (the strip) know.
    refresh(projectId).catch(() => {})
    // Only what Frank is confident about arrives here; nothing is filled in with a default.
    mergeFingerprint(info.hints)
    // One question at a time, the more important first. Never a list of things Frank is unsure about.
    const question = info.unsureAbout.includes("mood")
      ? " Does it feel bright and lifting to you, or heavier and deeper?"
      : info.unsureAbout.includes("speed")
        ? " Should it move along with a bit of push, or stay slow and easy?"
        : ""
    sayAsFrank(`Lovely, I'll build around your tune.${question} While you think, let me play you a first sound.`)
    void runTextureGeneration()
  }

  function handleRhythmConfirmed(hints: Partial<MusicalFingerprint>) {
    const clean = Object.fromEntries(Object.entries(hints).filter(([, v]) => v !== undefined)) as Partial<MusicalFingerprint>
    mergeFingerprint(clean)
    sayAsFrank("Lovely, I'll build the drums around your rhythm. While you think, let me play you a first sound.")
    void runTextureGeneration()
  }

  async function keepDirection(d: Direction) {
    // Lock in the direction the person chose as the reference for the feeling.
    fingerprintRef.current = { ...fingerprintRef.current, reference_texture_id: d.id }
    try {
      const saved = await saveFingerprint(projectId, fingerprintRef.current as MusicalFingerprint, summaryRef.current)
      updateActiveState({ active_fingerprint_id: saved.id })
      setKeptHere(d.id)
      setSuggestedId(null)
      void loadSong(projectId)
      say(
        "Locked in. Whenever you're ready, we can take this feeling into the Music room.",
        <ChangeLine material="feel">Feeling kept: Direction {d.number}</ChangeLine>,
      )
    } catch {
      say("I couldn't save that direction just now. Want to try keeping it again?")
    }
  }

  function notThis(d: Direction) {
    setAside(d.id)
    void handleSend("That one isn't quite it.")
  }

  function retry(d: Direction) {
    remove(d.id)
    void runTextureGeneration()
  }

  // ─── What Frank is saying on the stage ───
  const router2music = () => router.push(`/${projectId}/beat`)
  let note: React.ReactNode
  let aside: React.ReactNode = undefined
  let answers: { label: string; onClick: () => void; disabled?: boolean }[] = []
  if (!directionsLoaded) {
    note = "Getting your directions ready."
  } else if (making) {
    note = "Finding a sound for you."
    aside = "It usually takes about 20 seconds. You can keep talking to Frank while it's made."
  } else if (keptId && ready.some((d) => d.id === keptId)) {
    const kept = ready.find((d) => d.id === keptId)!
    note = `Direction ${kept.number} is the feeling of your song. Want to hear the music Frank builds from it?`
    answers = [
      { label: "Build the music", onClick: router2music },
      { label: "Keep exploring", onClick: () => void handleSend("I'd like to explore a little more.") },
    ]
  } else if (ready.length > 0) {
    note = "Play each direction and tell me which feels closest. Anything you hear that is off, say so."
    aside = lastWords ? <>You said: “{lastWords}”</> : undefined
    answers = [
      { label: "Make it simpler", onClick: () => void handleSend("Can it be simpler, with less going on?") },
      { label: "Try something different", onClick: () => void handleSend("Try something quite different.") },
    ]
  } else {
    note = "Tell me how your song should feel, in your own words. Or show me by humming a tune or tapping a rhythm."
  }

  const ordered = [...directions].reverse() // newest first; nothing is ever dropped
  // Never show the first-run question until we know there are no directions yet (no flash of an empty room).
  const showAsk = directionsLoaded && ready.length === 0 && !making

  return (
    <div className="flex h-full">
      <div className="flex min-w-0 flex-1 flex-col gap-7 overflow-y-auto px-10 py-8">
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-feel" />
          <h1 className="text-base font-medium text-ink">Feeling</h1>
          <span className="text-sm text-ink-2">Find how the song should feel</span>
        </div>

        <FrankNote aside={aside} answers={answers} material="feel">
          {note}
        </FrankNote>

        {showAsk && (
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault()
              const text = stageText.trim()
              if (!text || isThinking) return
              setStageText("")
              void handleSend(text)
            }}
          >
            <label htmlFor="feeling-ask" className="text-sm font-medium text-ink-2">
              How should it feel?
            </label>
            <div className="flex items-end gap-3">
              <textarea
                id="feeling-ask"
                value={stageText}
                onChange={(e) => setStageText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    e.currentTarget.form?.requestSubmit()
                  }
                }}
                rows={2}
                autoFocus
                placeholder="Walking home alone after a party, slow and warm, a little lonely…"
                className="min-h-[56px] max-w-xl flex-1 resize-none rounded-md bg-raised px-3 py-2.5 font-written text-[17px] leading-[25px] text-words placeholder:font-sans placeholder:text-base placeholder:text-ink-3"
              />
              <button
                type="submit"
                disabled={!stageText.trim() || isThinking}
                className="h-10 rounded-md bg-frank px-5 text-base font-medium text-ground hover:bg-frank/90 disabled:bg-raised disabled:text-ink-3"
              >
                {isThinking ? "Listening…" : "Play me a first sound"}
              </button>
            </div>
          </form>
        )}

        <section aria-labelledby="bench-heading">
          <h2 id="bench-heading" className="mb-3 text-xs font-semibold uppercase tracking-[0.06em] text-ink-3">
            Directions
          </h2>
          {ordered.length === 0 ? (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
              {[0, 1, 2].map((i) => (
                <div key={i} aria-hidden="true" className="flex min-h-[236px] flex-col justify-between rounded-md border border-dashed border-ink-3/70 p-4">
                  <span className="font-written text-xl text-ink-3">Direction {i + 1}</span>
                  <div className="h-16 w-full rounded-sm border border-dashed border-ink-3/40" />
                  <span className="text-sm text-ink-3">{directionsLoaded ? "Frank will play it here" : "Looking for your directions…"}</span>
                </div>
              ))}
            </div>
          ) : (
            <ul className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
              {ordered.map((d) => (
                <li key={d.id}>
                  <DirectionCard
                    direction={d}
                    kept={d.id === keptId}
                    primary={
                      d.status === "ready" &&
                      d.id !== keptId &&
                      (playing && currentTrackId === d.id ? true : !playing && d.id === suggestedId)
                    }
                    onKeep={keepDirection}
                    onNotThis={notThis}
                    onRetry={retry}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Show Frank instead of telling him" className="flex flex-wrap items-center gap-3 pb-4">
          <span className="text-base text-ink-2">Or show me:</span>
          <HumIntake projectId={projectId} onConfirmed={handleTuneConfirmed} onSay={sayAsFrank} appearance="stage" />
          <RhythmIntake projectId={projectId} onConfirmed={handleRhythmConfirmed} onSay={sayAsFrank} appearance="stage" />
        </section>
      </div>

      <ConversationPanel
        projectId={projectId}
        room="feel"
        material="feel"
        emptyText="Tell me how the song should feel."
        turns={turns}
        onSend={handleSend}
        isThinking={isThinking}
        placeholder="Describe how it should feel…"
      />
    </div>
  )
}
