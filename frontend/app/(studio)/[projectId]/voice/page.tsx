"use client"

/**
 * Voice Room — the most personal layer. Record as many takes as you need,
 * compare them, and let Frank help: tune a take, build the best version from
 * several, or add a harmony. The original of every take is always kept.
 */

import { useEffect, useRef, useState, useCallback } from "react"
import { useParams } from "next/navigation"
import {
  ConversationPanel,
  type ChatTurn,
} from "@/components/conversation/ConversationPanel"
import { VocalRecorder } from "@/components/audio/VocalRecorder"
import { PitchDisplay } from "@/components/audio/PitchDisplay"
import { Button } from "@/components/ui/button"
import {
  uploadTake,
  listTakes,
  correctPitch,
  buildComp,
  generateHarmony,
  setActiveVocal,
  sendVoiceMessage,
  type VocalTake,
} from "@/lib/api/voice"
import { listBeatVersions } from "@/lib/api/beat"
import { pollJob } from "@/lib/api/jobs"
import { useProjectStore } from "@/store/project"
import type { ConversationMessage, ConversationAction } from "@/types/api"
import { Mic2, Play, Pause, Sparkles, Wand2, Check } from "lucide-react"
import { cn } from "@/lib/utils"

export default function VoiceRoomPage() {
  const params = useParams()
  const projectId = params.projectId as string
  const { activeState, updateActiveState, revision } = useProjectStore()

  const [takes, setTakes] = useState<VocalTake[]>([])
  const [beatUrl, setBeatUrl] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([])
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [isThinking, setIsThinking] = useState(false)
  const [playingUrl, setPlayingUrl] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const historyRef = useRef<ConversationMessage[]>([])

  const refreshTakes = useCallback(async () => {
    const t = await listTakes(projectId)
    setTakes(t)
    return t
  }, [projectId])

  // Greeting — once, so the conversation isn't reset on every re-sync.
  useEffect(() => {
    setTurns([
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          "Whenever you're ready, record your take. Sing it as many times as you like — I'll keep every one. When you want, I can tune a take, blend the best bits together, or add a harmony.",
      },
    ])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  // Data load — re-runs whenever the shared state refreshes (e.g. the user
  // navigated in from the Beat Room having just built a beat), so the beat to
  // sing over and the take list stay current.
  useEffect(() => {
    refreshTakes()
    listBeatVersions(projectId).then((vs) => {
      const activeId = activeState?.active_beat_version_id
      const active = vs.find((v) => v.id === activeId) ?? vs[0]
      setBeatUrl(active?.render_url ?? null)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, revision])

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

  async function handleRecorded(blob: Blob, ext: string) {
    setUploading(true)
    try {
      const { take, analysis_job_id } = await uploadTake(projectId, blob, ext)
      setTakes((t) => [take, ...t])
      // The backend makes a new recording the active vocal — mirror that into
      // the shared store so the Beat and Mix Rooms know a vocal now exists.
      updateActiveState({ active_vocal_id: take.id })
      // Pitch analysis runs in the background — refresh when it lands
      pollJob(analysis_job_id)
        .then(() => refreshTakes())
        .catch(() => {})
    } catch {
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Something went wrong saving that take — want to try again?",
        },
      ])
    } finally {
      setUploading(false)
    }
  }

  function toggleCompare(takeId: string) {
    setSelectedForCompare((sel) =>
      sel.includes(takeId)
        ? sel.filter((id) => id !== takeId)
        : [...sel, takeId],
    )
  }

  async function runJob(
    start: () => Promise<{ job_id: string }>,
    pending: string,
    done: string,
  ) {
    setBusy(true)
    const id = crypto.randomUUID()
    setTurns((t) => [...t, { id, role: "assistant", content: pending }])
    try {
      const { job_id } = await start()
      await pollJob(job_id)
      await refreshTakes()
      setTurns((t) =>
        t.map((x) => (x.id === id ? { ...x, content: done } : x)),
      )
    } catch {
      setTurns((t) =>
        t.map((x) =>
          x.id === id
            ? { ...x, content: "Frank hit a snag there — want to try again?" }
            : x,
        ),
      )
    } finally {
      setBusy(false)
    }
  }

  async function dispatchAction(action: ConversationAction) {
    const p = action.params as Record<string, unknown>
    const activeTakeId = activeState?.active_vocal_id ?? takes[0]?.id
    switch (action.type) {
      case "correct_pitch":
        if (!activeTakeId) return
        await runJob(
          () => correctPitch(projectId, activeTakeId, (p.mode as "light" | "moderate" | "full") ?? "light"),
          "Tuning it up…",
          "Done — compare it with your original and keep whichever you like.",
        )
        break
      case "build_comp": {
        const ids = takes.map((t) => t.id)
        if (ids.length < 2) return
        await runJob(
          () => buildComp(projectId, ids),
          "Putting together the best version…",
          "Here's a version using the best moments from your takes — have a listen.",
        )
        break
      }
      case "add_harmony":
        if (!activeTakeId) return
        await runJob(
          () => generateHarmony(projectId, activeTakeId, (p.type as "above" | "below" | "both") ?? "above"),
          "Adding a harmony…",
          "I added a second voice to go with yours — it's in your takes now.",
        )
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
      const res = await sendVoiceMessage(
        projectId,
        message,
        historyRef.current.slice(0, -1),
      )
      setTurns((t) => [
        ...t,
        { id: crypto.randomUUID(), role: "assistant", content: res.message },
      ])
      historyRef.current.push({ role: "assistant", content: res.message })
      setIsThinking(false)
      for (const action of res.actions) await dispatchAction(action)
    } catch {
      setIsThinking(false)
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Frank stepped away for a second — say that again?",
        },
      ])
    }
  }

  async function chooseActive(take: VocalTake) {
    await setActiveVocal(projectId, take.id, "take")
    updateActiveState({ active_vocal_id: take.id })
  }

  const activeTakeId = activeState?.active_vocal_id ?? null

  return (
    <div className="flex h-screen">
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="border-b border-border px-8 py-3">
          <h1 className="text-sm font-semibold text-foreground">Voice Room</h1>
          <p className="text-xs text-muted-foreground">Record your voice</p>
        </div>

        <div className="flex-1 overflow-y-auto px-8 py-8">
          {/* Recorder */}
          <div className="mb-10">
            <VocalRecorder
              beatUrl={beatUrl}
              uploading={uploading}
              onRecorded={handleRecorded}
            />
          </div>

          {/* Takes */}
          {takes.length > 0 && (
            <div className="mx-auto max-w-2xl">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-medium text-muted-foreground">
                  Your takes ({takes.length})
                </h2>
                {selectedForCompare.length >= 2 && (
                  <Button
                    size="sm"
                    disabled={busy}
                    onClick={() =>
                      runJob(
                        () => buildComp(projectId, selectedForCompare),
                        "Putting together the best version…",
                        "Here's a blend of the takes you picked — have a listen.",
                      )
                    }
                  >
                    <Wand2 className="h-3.5 w-3.5" />
                    Blend {selectedForCompare.length} takes
                  </Button>
                )}
              </div>

              <div className="flex flex-col gap-3">
                {takes.map((take) => (
                  <div
                    key={take.id}
                    className={cn(
                      "rounded-xl border p-4 transition-colors",
                      take.id === activeTakeId
                        ? "border-primary/40 bg-primary/5"
                        : "border-border bg-card",
                    )}
                  >
                    <div className="mb-3 flex items-center gap-3">
                      <button
                        onClick={() => playUrl(take.processed_url ?? take.audio_url)}
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary hover:bg-primary/25"
                        aria-label="Play take"
                      >
                        {playingUrl === (take.processed_url ?? take.audio_url) ? (
                          <Pause className="h-4 w-4" />
                        ) : (
                          <Play className="h-4 w-4 translate-x-px" />
                        )}
                      </button>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-foreground">{take.label}</p>
                        {take.processed_url && (
                          <p className="text-[11px] text-primary/70">tuned</p>
                        )}
                      </div>

                      {/* Compare checkbox */}
                      <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedForCompare.includes(take.id)}
                          onChange={() => toggleCompare(take.id)}
                          className="accent-amber-500"
                        />
                        pick
                      </label>

                      {take.id === activeTakeId ? (
                        <span className="flex items-center gap-1 text-xs text-primary">
                          <Check className="h-3.5 w-3.5" /> using
                        </span>
                      ) : (
                        <button
                          onClick={() => chooseActive(take)}
                          className="text-xs text-muted-foreground hover:text-primary"
                        >
                          use this
                        </button>
                      )}
                    </div>

                    {/* Pitch display */}
                    <PitchDisplay pitchData={take.pitch_data} />

                    {/* Quick actions */}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() =>
                          runJob(
                            () => correctPitch(projectId, take.id, "light"),
                            "Tuning the obvious bits…",
                            "Tuned the parts that were a little off — compare and keep what you like.",
                          )
                        }
                        className="h-7 text-xs"
                      >
                        <Sparkles className="h-3 w-3" />
                        Tune it up
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() =>
                          runJob(
                            () => generateHarmony(projectId, take.id, "above"),
                            "Adding a harmony…",
                            "Added a second voice above yours — it's in your takes.",
                          )
                        }
                        className="h-7 text-xs"
                      >
                        <Wand2 className="h-3 w-3" />
                        Add a harmony
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <ConversationPanel
        emptyText="Getting your takes ready…"
        turns={turns}
        onSend={handleSend}
        isThinking={isThinking}
        placeholder="Ask Frank for help with your voice…"
      />
    </div>
  )
}
