"use client"

/**
 * Mix Room — where the voice, the beat, and any harmony come together into one
 * song. The user shapes the balance entirely by listening and talking. Every
 * adjustment renders a new mix; nothing is overwritten.
 */

import { useEffect, useRef, useState, useCallback } from "react"
import { useParams } from "next/navigation"
import {
  ConversationPanel,
  type ChatTurn,
} from "@/components/conversation/ConversationPanel"
import { StemBalance } from "@/components/studio/StemBalance"
import { MixVersions } from "@/components/studio/MixVersions"
import { Button } from "@/components/ui/button"
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
import type { ConversationMessage } from "@/types/api"
import { SlidersHorizontal, Play, Pause, Loader2 } from "lucide-react"

const DEFAULT_PARAMS: Partial<MixParams> = {
  vocal_gain_db: 0,
  beat_gain_db: -6,
  harmony_gain_db: -4,
  harmony_enabled: true,
  vocal_effects: [],
  beat_effects: [],
  section_gain_db: {},
}

export default function MixRoomPage() {
  const params = useParams()
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
  const [playing, setPlaying] = useState(false)

  const mixParamsRef = useRef<Partial<MixParams>>({ ...DEFAULT_PARAMS })
  const historyRef = useRef<ConversationMessage[]>([])
  const audioRef = useRef<HTMLAudioElement | null>(null)
  // Guards so we greet once and auto-assemble the first mix only once.
  const greetedRef = useRef(false)
  const autoAssembledRef = useRef(false)

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
        (t) => !(t.label ?? "").toLowerCase().startsWith("harmony"),
      )
      const harmonies = takes.filter((t) =>
        (t.label ?? "").toLowerCase().startsWith("harmony"),
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
                "Here's how it sounds right now. Tell me what you'd change — is the voice sitting right? Too much beat? Something feel off? I'll adjust and we'll listen again.",
            },
          ])
        } else if (haveVocal && haveBeat) {
          setTurns([
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content: "Let me put your voice and the beat together. One moment…",
            },
          ])
        } else {
          const missing = !haveVocal ? "a vocal" : "a beat"
          setTurns([
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content: `We need ${missing} before we can mix. Pop back to ${!haveVocal ? "the Voice Room" : "the Beat Room"} and I'll be ready when you are.`,
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

  useEffect(() => {
    audioRef.current?.pause()
    setPlaying(false)
    if (!activeVersion?.render_url) {
      audioRef.current = null
      return
    }
    const audio = new Audio(activeVersion.render_url)
    audio.addEventListener("ended", () => setPlaying(false))
    audioRef.current = audio
    return () => audio.pause()
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

  async function doRender(mixParams: Partial<MixParams>, quality: "preview" | "full" = "preview") {
    setRendering(true)
    try {
      const { job_id } = await renderMix(projectId, mixParams, quality)
      await pollJob(job_id)
      await loadVersions()
    } catch {
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Frank couldn't put the mix together just then — want to try again?",
        },
      ])
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

  return (
    <div className="flex h-screen">
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="border-b border-border px-8 py-3">
          <h1 className="text-sm font-semibold text-foreground">Mix Room</h1>
          <p className="text-xs text-muted-foreground">
            Bring it all together
          </p>
        </div>

        <div className="flex-1 overflow-y-auto px-8 py-8">
          <div className="mx-auto max-w-xl">
            {/* Transport */}
            <div className="mb-8 flex flex-col items-center gap-4">
              <button
                onClick={togglePlay}
                disabled={!hasMix || rendering}
                className="flex h-16 w-16 items-center justify-center rounded-full bg-primary text-primary-foreground transition-transform hover:scale-105 disabled:opacity-40"
                aria-label={playing ? "Pause" : "Play"}
              >
                {rendering ? (
                  <Loader2 className="h-6 w-6 animate-spin" />
                ) : playing ? (
                  <Pause className="h-6 w-6" />
                ) : (
                  <Play className="h-7 w-7 translate-x-0.5" />
                )}
              </button>
              <p className="text-sm text-muted-foreground">
                {rendering
                  ? "Putting the mix together…"
                  : hasMix
                    ? activeVersion?.label
                    : "No mix yet"}
              </p>
              {hasMix && !rendering && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => doRender(mixParamsRef.current, "full")}
                >
                  Render full quality
                </Button>
              )}
            </div>

            {/* Stem balance */}
            {(hasVocal || hasBeat) && (
              <div className="mb-8">
                <StemBalance
                  hasVocal={hasVocal}
                  hasBeat={hasBeat}
                  hasHarmony={hasHarmony}
                  harmonyEnabled={mixParamsRef.current.harmony_enabled ?? true}
                  onToggleHarmony={handleToggleHarmony}
                />
              </div>
            )}

            {/* Versions */}
            <MixVersions
              versions={versions}
              activeVersionId={activeVersion?.id ?? null}
              onSetActive={handleSetActive}
            />
          </div>
        </div>
      </div>

      <ConversationPanel
        emptyText="Getting your mix ready…"
        turns={turns}
        onSend={handleSend}
        isThinking={isThinking}
        placeholder="Tell Frank what to change…"
      />
    </div>
  )
}
