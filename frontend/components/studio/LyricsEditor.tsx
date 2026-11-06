"use client"

/**
 * LyricsEditor — the notebook at the heart of the Idea Room.
 * A quiet, spacious place to write. Auto-saves after 2 seconds of stillness.
 * Every save that changes the words becomes a new version (handled server-side).
 */

import { useEffect, useRef, useState, useCallback } from "react"
import { Textarea } from "@/components/ui/textarea"
import { saveLyrics } from "@/lib/api/lyrics"
import { useProjectStore } from "@/store/project"
import { Check, Loader2 } from "lucide-react"

const SECTION_HINTS = ["Verse", "Chorus", "Bridge", "Hook", "Outro"]
const AUTOSAVE_DELAY_MS = 2000

type SaveState = "idle" | "saving" | "saved"

interface LyricsEditorProps {
  projectId: string
  initialContent: string
  onSelectionChange?: (selectedText: string) => void
  onContentChange?: (content: string) => void
  onVersionSaved?: (versionId: string) => void
}

export function LyricsEditor({
  projectId,
  initialContent,
  onSelectionChange,
  onContentChange,
  onVersionSaved,
}: LyricsEditorProps) {
  const [content, setContent] = useState(initialContent)
  const [saveState, setSaveState] = useState<SaveState>("idle")
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSavedRef = useRef(initialContent)
  const { updateActiveState } = useProjectStore()

  // Keep content in sync if the active version changes externally (e.g. restore)
  useEffect(() => {
    setContent(initialContent)
    lastSavedRef.current = initialContent
  }, [initialContent])

  const doSave = useCallback(
    async (text: string) => {
      if (text === lastSavedRef.current) {
        setSaveState("idle")
        return
      }
      setSaveState("saving")
      try {
        const version = await saveLyrics(projectId, text)
        lastSavedRef.current = text
        updateActiveState({ active_lyrics_id: version.id })
        onVersionSaved?.(version.id)
        setSaveState("saved")
        // Fade the "saved" indicator after a moment
        setTimeout(() => setSaveState("idle"), 2000)
      } catch {
        setSaveState("idle")
      }
    },
    [projectId, updateActiveState, onVersionSaved],
  )

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const text = e.target.value
    setContent(text)
    onContentChange?.(text)

    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => doSave(text), AUTOSAVE_DELAY_MS)
  }

  function handleSelect() {
    const el = textareaRef.current
    if (!el) return
    const selected = el.value.substring(el.selectionStart, el.selectionEnd)
    if (selected.trim()) onSelectionChange?.(selected)
  }

  // Save on unmount if there are pending changes
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [])

  return (
    <div className="flex h-full flex-col">
      {/* Save indicator — subtle, top right */}
      <div className="flex items-center justify-end px-8 pt-6 h-8">
        {saveState === "saving" && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground/60">
            <Loader2 className="h-3 w-3 animate-spin" />
            Saving
          </span>
        )}
        {saveState === "saved" && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground/60">
            <Check className="h-3 w-3 text-primary" />
            Saved
          </span>
        )}
      </div>

      {/* The notebook */}
      <div className="flex-1 px-8 pb-8">
        <Textarea
          ref={textareaRef}
          value={content}
          onChange={handleChange}
          onSelect={handleSelect}
          placeholder={
            "Start writing.\n\nYou can mark sections however you like — " +
            SECTION_HINTS.join(", ") +
            ".\n\nFrank is listening whenever you want help."
          }
          className="h-full min-h-full resize-none border-none bg-transparent px-0 text-lg leading-relaxed shadow-none focus-visible:ring-0 placeholder:text-muted-foreground/30"
          aria-label="Lyrics editor"
        />
      </div>
    </div>
  )
}
