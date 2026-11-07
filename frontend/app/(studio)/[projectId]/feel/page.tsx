"use client"

/**
 * Feel Lab — where the song finds its feeling.
 * Conversational feel discovery + humming + texture playback. The musical
 * fingerprint is built quietly as the conversation goes; it's never shown.
 */

import { useEffect, useRef, useState } from "react"
import { useParams } from "next/navigation"
import {
  ConversationPanel,
  type ChatTurn,
} from "@/components/conversation/ConversationPanel"
import { TexturePlayer } from "@/components/audio/TexturePlayer"
import { HumButton } from "@/components/studio/HumButton"
import { Button } from "@/components/ui/button"
import {
  sendFeelMessage,
  generateTexture,
  saveFingerprint,
  getFingerprint,
  type HumAnalysisResult,
} from "@/lib/api/feel"
import { pollJob } from "@/lib/api/jobs"
import { useProjectStore } from "@/store/project"
import type { MusicalFingerprint } from "@/types/project"
import type { ConversationMessage } from "@/types/api"
import { Sparkles, Check } from "lucide-react"

export default function FeelLabPage() {
  const params = useParams()
  const projectId = params.projectId as string
  const { updateActiveState } = useProjectStore()

  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [isThinking, setIsThinking] = useState(false)
  const [directionApproved, setDirectionApproved] = useState(false)

  // The evolving fingerprint and conversation history (read at send time)
  const fingerprintRef = useRef<Partial<MusicalFingerprint>>({})
  const historyRef = useRef<ConversationMessage[]>([])
  const summaryRef = useRef<string>("")
  // The most recently generated texture id, so approval can reference it
  const lastTextureIdRef = useRef<string | null>(null)

  // Opening: load any existing fingerprint (return visit) or greet fresh.
  useEffect(() => {
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
              content:
                `Welcome back.${recap} Want to keep going from here, or try something different?`,
            },
          ])
        } else {
          setTurns([
            {
              id: crypto.randomUUID(),
              role: "assistant",
              content:
                "Let's find the feeling of your song. Don't worry about music words — just tell me how it should feel. Where does it take you?",
            },
          ])
        }
      })
      .catch(() => {
        setTurns([
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content:
              "Let's find the feeling of your song. Don't worry about music words — just tell me how it should feel. Where does it take you?",
          },
        ])
      })
  }, [projectId])

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
    const placeholderId = crypto.randomUUID()
    setTurns((t) => [
      ...t,
      {
        id: placeholderId,
        role: "assistant",
        content: "Finding a sound…",
      },
    ])

    try {
      const { job_id } = await generateTexture(projectId, fingerprintRef.current)
      const result = await pollJob(job_id)
      const payload = result.result as {
        audio_url?: string
        texture_id?: string
      }
      const audioUrl = payload?.audio_url
      if (payload?.texture_id) lastTextureIdRef.current = payload.texture_id

      setTurns((t) =>
        t.map((turn) =>
          turn.id === placeholderId
            ? {
                ...turn,
                content: "Here's a direction — tell me how it sits with you.",
                actionBlock: audioUrl ? (
                  <TexturePlayer audioUrl={audioUrl} />
                ) : undefined,
              }
            : turn,
        ),
      )
    } catch {
      setTurns((t) =>
        t.map((turn) =>
          turn.id === placeholderId
            ? {
                ...turn,
                content:
                  "Frank couldn't find that sound just now — want to try again?",
              }
            : turn,
        ),
      )
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
      const res = await sendFeelMessage(
        projectId,
        message,
        fingerprintRef.current,
        historyRef.current.slice(0, -1),
      )

      // Merge the fingerprint update (list fields accumulate, not clobber)
      mergeFingerprint(res.fingerprint_update)

      setTurns((t) => [
        ...t,
        { id: crypto.randomUUID(), role: "assistant", content: res.message },
      ])
      historyRef.current.push({ role: "assistant", content: res.message })
      summaryRef.current = res.message

      // Act on the two possible Feel Lab actions
      const wantsTexture = res.actions.some((a) => a.type === "generate_texture")
      const approved = res.actions.some((a) => a.type === "approve_direction")

      if (wantsTexture) {
        setIsThinking(false)
        await runTextureGeneration()
        return
      }
      if (approved) {
        setDirectionApproved(true)
      }
    } catch {
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Frank lost the thread for a second — say that again?",
        },
      ])
    } finally {
      setIsThinking(false)
    }
  }

  function handleHumAnalyzed(result: HumAnalysisResult) {
    // Seed the fingerprint with the hum's hints and the stored hum reference
    mergeFingerprint(result.analysis.fingerprint_hints)
    fingerprintRef.current = {
      ...fingerprintRef.current,
      hum_reference_file: result.audio_url,
    }
    setTurns((t) => [
      ...t,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `I hear something ${describeHum(result)}. Let me find a direction that feels like that.`,
      },
    ])
    // Immediately offer a texture based on the hum
    runTextureGeneration()
  }

  async function handleApproveAndSave() {
    // Lock in the texture the user approved as the reference for this direction
    if (lastTextureIdRef.current) {
      fingerprintRef.current = {
        ...fingerprintRef.current,
        reference_texture_id: lastTextureIdRef.current,
      }
    }
    try {
      const saved = await saveFingerprint(
        projectId,
        fingerprintRef.current as MusicalFingerprint,
        summaryRef.current,
      )
      updateActiveState({ active_fingerprint_id: saved.id })
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            "Locked in. Whenever you're ready, we can take this feeling into the Beat Room.",
        },
      ])
      setDirectionApproved(false)
    } catch {
      // ignore; user can retry
    }
  }

  return (
    <div className="flex h-screen">
      {/* Main area */}
      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-border px-8 py-3">
          <div>
            <h1 className="text-sm font-semibold text-foreground">Feel Lab</h1>
            <p className="text-xs text-muted-foreground">
              Find the feeling of your song
            </p>
          </div>
          {directionApproved && (
            <Button size="sm" onClick={handleApproveAndSave}>
              <Check className="h-4 w-4" />
              Keep this direction
            </Button>
          )}
        </div>

        {/* Centerpiece — a quiet, inviting space */}
        <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
          <div className="rounded-full bg-primary/10 p-6">
            <Sparkles className="h-10 w-10 text-primary" />
          </div>
          <p className="mt-6 max-w-sm text-sm text-muted-foreground leading-relaxed">
            Talk with Frank on the right about how your song should feel. You can
            also hum something — whatever's easier. Frank will play you sounds as
            you go.
          </p>
        </div>
      </div>

      {/* Conversation */}
      <ConversationPanel
        turns={turns}
        onSend={handleSend}
        isThinking={isThinking}
        placeholder="Describe how it should feel…"
        inputAccessory={
          <HumButton
            projectId={projectId}
            onAnalyzed={handleHumAnalyzed}
            onError={(msg) =>
              setTurns((t) => [
                ...t,
                { id: crypto.randomUUID(), role: "assistant", content: msg },
              ])
            }
          />
        }
      />
    </div>
  )
}

function describeHum(result: HumAnalysisResult): string {
  const { register, pitch_movement, energy_level } = result.analysis
  const energy = energy_level > 0.6 ? "with some energy" : "gentle and calm"
  const movement =
    pitch_movement === "rising"
      ? "lifting upward"
      : pitch_movement === "falling"
        ? "settling down"
        : pitch_movement === "wandering"
          ? "wandering and searching"
          : "steady"
  const reg =
    register === "low" ? "low and warm" : register === "high" ? "bright" : "in the middle"
  return `${reg}, ${movement}, ${energy}`
}
