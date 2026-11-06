"use client"

/**
 * Idea Room — where a song starts.
 * Lyrics editor + AI co-writer + draft history + voice memo capture.
 */

import { useEffect, useState, useCallback, useRef } from "react"
import { useParams } from "next/navigation"
import { LyricsEditor } from "@/components/studio/LyricsEditor"
import { LyricsVersionHistory } from "@/components/studio/LyricsVersionHistory"
import { VoiceMemoButton } from "@/components/studio/VoiceMemoButton"
import {
  ConversationPanel,
  type ChatTurn,
} from "@/components/conversation/ConversationPanel"
import { Button } from "@/components/ui/button"
import { listLyricsVersions, setActiveLyrics } from "@/lib/api/lyrics"
import { sendIdeaMessage } from "@/lib/api/conversation"
import { useProjectStore } from "@/store/project"
import type { LyricsVersion } from "@/types/project"
import type { ConversationMessage } from "@/types/api"
import { History, Plus } from "lucide-react"

export default function IdeaRoomPage() {
  const params = useParams()
  const projectId = params.projectId as string
  const { activeState } = useProjectStore()

  const [versions, setVersions] = useState<LyricsVersion[]>([])
  const [editorContent, setEditorContent] = useState("")
  const [showHistory, setShowHistory] = useState(false)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [isThinking, setIsThinking] = useState(false)

  // Live references the conversation reads at send time
  const currentLyricsRef = useRef("")
  const selectedTextRef = useRef<string | undefined>(undefined)
  const historyRef = useRef<ConversationMessage[]>([])

  // Load existing lyrics versions on entry
  useEffect(() => {
    listLyricsVersions(projectId).then((vs) => {
      setVersions(vs)
      if (vs.length > 0) {
        // Active version is the newest (vs is sorted desc)
        const active = vs[0]
        setEditorContent(active.content)
        currentLyricsRef.current = active.content
      }
    })
  }, [projectId])

  const refreshVersions = useCallback(async () => {
    const vs = await listLyricsVersions(projectId)
    setVersions(vs)
  }, [projectId])

  function handleContentChange(content: string) {
    currentLyricsRef.current = content
  }

  function handleSelectionChange(text: string) {
    selectedTextRef.current = text
  }

  // After the editor saves a new version, refresh the draft list so the
  // history panel stays current. This is driven by the save event rather than
  // blind polling, so it never clobbers what the user is actively typing.
  function handleVersionSaved() {
    refreshVersions()
  }

  async function handleRestore(version: LyricsVersion) {
    setEditorContent(version.content)
    currentLyricsRef.current = version.content
    await setActiveLyrics(projectId, version.id)
    setShowHistory(false)
    await refreshVersions()
  }

  function addToEditor(content: string, sectionLabel?: string) {
    const prefix = currentLyricsRef.current.trim() ? "\n\n" : ""
    const section = sectionLabel ? `[${sectionLabel}]\n` : ""
    const next = currentLyricsRef.current + prefix + section + content
    setEditorContent(next)
    currentLyricsRef.current = next
  }

  async function handleSend(message: string) {
    const userTurn: ChatTurn = {
      id: crypto.randomUUID(),
      role: "user",
      content: message,
    }
    setTurns((t) => [...t, userTurn])
    historyRef.current.push({ role: "user", content: message })
    setIsThinking(true)

    try {
      const res = await sendIdeaMessage(projectId, {
        message,
        currentLyrics: currentLyricsRef.current,
        selectedText: selectedTextRef.current,
        history: historyRef.current.slice(0, -1),
      })

      // Build the assistant turn, attaching a suggestion block if present
      const suggestion = res.actions.find((a) => a.type === "suggest_lyrics")
      const assistantTurn: ChatTurn = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: res.message,
        actionBlock: suggestion ? (
          <SuggestionBlock
            content={String(suggestion.params.content ?? "")}
            sectionLabel={
              suggestion.params.section_label
                ? String(suggestion.params.section_label)
                : undefined
            }
            onAdd={(c, s) => addToEditor(c, s)}
          />
        ) : undefined,
      }
      setTurns((t) => [...t, assistantTurn])
      historyRef.current.push({ role: "assistant", content: res.message })
      selectedTextRef.current = undefined
    } catch {
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Frank got distracted for a second — try saying that again?",
        },
      ])
    } finally {
      setIsThinking(false)
    }
  }

  const activeVersionId = activeState?.active_lyrics_id ?? versions[0]?.id ?? null

  return (
    <div className="flex h-screen">
      {/* Editor column */}
      <div className="flex flex-1 flex-col">
        {/* Top bar */}
        <div className="flex items-center justify-between border-b border-border px-8 py-3">
          <div>
            <h1 className="text-sm font-semibold text-foreground">Idea Room</h1>
            <p className="text-xs text-muted-foreground">Write your song</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowHistory((s) => !s)}
            className="text-muted-foreground"
          >
            <History className="h-4 w-4" />
            Drafts ({versions.length})
          </Button>
        </div>

        <div className="flex-1 overflow-hidden">
          <LyricsEditor
            projectId={projectId}
            initialContent={editorContent}
            onContentChange={handleContentChange}
            onSelectionChange={handleSelectionChange}
            onVersionSaved={handleVersionSaved}
          />
        </div>
      </div>

      {/* History panel (toggleable) */}
      {showHistory && (
        <LyricsVersionHistory
          versions={versions}
          activeVersionId={activeVersionId}
          onRestore={handleRestore}
          onClose={() => setShowHistory(false)}
          onLabelUpdated={(id, label) =>
            setVersions((vs) =>
              vs.map((v) => (v.id === id ? { ...v, label } : v)),
            )
          }
        />
      )}

      {/* Conversation panel */}
      <ConversationPanel
        turns={turns}
        onSend={handleSend}
        isThinking={isThinking}
        placeholder="Ask for a rhyme, a line, a chorus…"
        inputAccessory={
          <VoiceMemoButton
            projectId={projectId}
            onTranscription={(text) => {
              setTurns((t) => [
                ...t,
                {
                  id: crypto.randomUUID(),
                  role: "assistant",
                  content: `Here's what I heard — want to use any of this?`,
                  actionBlock: (
                    <SuggestionBlock
                      content={text}
                      onAdd={(c) => addToEditor(c)}
                    />
                  ),
                },
              ])
            }}
            onError={(message) => {
              setTurns((t) => [
                ...t,
                {
                  id: crypto.randomUUID(),
                  role: "assistant",
                  content: message,
                },
              ])
            }}
          />
        }
      />
    </div>
  )
}

// ─────────────────────────────────────────────
// A lyric suggestion block shown inside the conversation
// ─────────────────────────────────────────────
function SuggestionBlock({
  content,
  sectionLabel,
  onAdd,
}: {
  content: string
  sectionLabel?: string
  onAdd: (content: string, sectionLabel?: string) => void
}) {
  // "resolved" captures whichever choice the user made: added or dismissed.
  const [resolved, setResolved] = useState<"added" | "ignored" | null>(null)

  if (resolved === "ignored") return null

  return (
    <div className="max-w-[90%] rounded-xl border border-primary/20 bg-primary/5 p-3">
      {sectionLabel && (
        <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-primary/70">
          {sectionLabel}
        </p>
      )}
      <pre className="whitespace-pre-wrap font-sans text-sm text-foreground leading-relaxed">
        {content}
      </pre>
      <div className="mt-2.5 flex items-center gap-2">
        {resolved === "added" ? (
          <span className="text-xs text-primary">Added to your lyrics</span>
        ) : (
          <>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                onAdd(content, sectionLabel)
                setResolved("added")
              }}
              className="h-7 text-xs"
            >
              <Plus className="h-3 w-3" />
              Add to editor
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setResolved("ignored")}
              className="h-7 text-xs text-muted-foreground"
            >
              Ignore
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
