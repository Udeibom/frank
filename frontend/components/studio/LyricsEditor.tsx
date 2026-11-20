"use client"

/**
 * LyricsEditor: the page at the heart of the Words room. The person's own words, set in the written face at
 * reading width, with nothing in the way. Saves itself after 2 seconds of stillness; every save that changes the
 * words becomes a new draft (server-side). Sections can be marked plainly ("Chorus" on its own line) or in
 * brackets; the margin outline shows the ones found.
 */

import { useEffect, useRef, useState, useCallback } from "react"
import { saveLyrics } from "@/lib/api/lyrics"
import { useProjectStore } from "@/store/project"

const AUTOSAVE_DELAY_MS = 2000

type SaveState = "idle" | "saving" | "saved" | "failed"

interface LyricsEditorProps {
  projectId: string
  initialContent: string
  onSelectionChange?: (selectedText: string) => void
  onContentChange?: (content: string) => void
  onVersionSaved?: (versionId: string, content: string) => void
}

export function LyricsEditor({ projectId, initialContent, onSelectionChange, onContentChange, onVersionSaved }: LyricsEditorProps) {
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

  // The page grows with the words, so the stage scrolls as one piece (no box inside a box).
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${Math.max(el.scrollHeight, 420)}px`
  }, [content])

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
        onVersionSaved?.(version.id, text)
        setSaveState("saved")
      } catch {
        // Say so: the words are still on the page, and the next pause tries again.
        setSaveState("failed")
      }
    },
    [projectId, updateActiveState, onVersionSaved],
  )

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const text = e.target.value
    setContent(text)
    onContentChange?.(text)
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => void doSave(text), AUTOSAVE_DELAY_MS)
  }

  function handleSelect() {
    const el = textareaRef.current
    if (!el) return
    const selected = el.value.substring(el.selectionStart, el.selectionEnd)
    if (selected.trim()) onSelectionChange?.(selected)
  }

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [])

  const status =
    saveState === "saving"
      ? "Saving…"
      : saveState === "saved"
        ? "Saved as a draft"
        : saveState === "failed"
          ? "Couldn't save just now. Your words are still here; I'll try again when you pause."
          : content.trim()
            ? "Saved"
            : ""

  return (
    <div className="flex flex-col">
      <p role="status" aria-live="polite" className={saveState === "failed" ? "mb-2 h-5 text-sm text-problem" : "mb-2 h-5 text-sm text-ink-3"}>
        {status}
      </p>
      <textarea
        ref={textareaRef}
        value={content}
        onChange={handleChange}
        onSelect={handleSelect}
        placeholder={
          "Start writing.\n\nA line, a feeling, a whole chorus. Mark a section by giving it its own line: Verse, Chorus, Bridge."
        }
        className="w-full resize-none overflow-hidden bg-transparent font-written text-xl leading-[1.6] text-ink placeholder:font-sans placeholder:text-base placeholder:leading-relaxed placeholder:text-ink-3 focus-visible:outline-none"
        aria-label="Your words"
        spellCheck
      />
    </div>
  )
}
