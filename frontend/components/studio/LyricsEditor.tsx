"use client"

/**
 * LyricsEditor: the page at the heart of the Words room. The person's own words, set in the written face at
 * reading width, with nothing in the way. Saves itself after 2 seconds of stillness; every save that changes the
 * words becomes a new draft (server-side). Sections can be marked plainly ("Chorus" on its own line) or in
 * brackets; the margin outline shows the ones found.
 *
 * Tiptap (frankenstein spec 14, requirement 5.1): one paragraph per line, so the words stay plain text. With
 * "Show the rhythm" on, each line shows how many beats it has, its words show their strong and soft syllables,
 * and lines that rhyme share a colour. The analysis comes from Frank's pronouncing dictionary on the server.
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { EditorContent, useEditor, type Editor } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import { Extension } from "@tiptap/core"
import { Plugin, PluginKey } from "@tiptap/pm/state"
import { Decoration, DecorationSet } from "@tiptap/pm/view"
import type { Node as PMNode } from "@tiptap/pm/model"
import { saveLyrics } from "@/lib/api/lyrics"
import { analyseLyrics, findRhymes } from "@/lib/api/organs"
import { useProjectStore } from "@/store/project"
import type { LyricLineSound, RhymeSuggestions } from "@/types/api"

const AUTOSAVE_DELAY_MS = 2000
const ANALYSE_DELAY_MS = 1200
const HEADING = /^\s*[[(]?\s*(intro|verse|pre-?chorus|chorus|hook|refrain|bridge|outro)\b[^\])]*[\])]?\s*:?\s*$/i

type SaveState = "idle" | "saving" | "saved" | "failed"

interface LyricsEditorProps {
  projectId: string
  initialContent: string
  onSelectionChange?: (selectedText: string) => void
  onContentChange?: (content: string) => void
  onVersionSaved?: (versionId: string, content: string) => void
}

/** Plain text <-> one paragraph per line. */
export function textToDoc(text: string) {
  return {
    type: "doc",
    content: text.split("\n").map((line) => (line ? { type: "paragraph", content: [{ type: "text", text: line }] } : { type: "paragraph" })),
  }
}

export function docToText(doc: PMNode): string {
  const lines: string[] = []
  doc.forEach((node) => lines.push(node.textContent))
  return lines.join("\n")
}

/** The analysed lines matched to the document's paragraphs (blank lines and headings are not analysed). */
export function matchLines(paragraphs: string[], analysed: LyricLineSound[]): (LyricLineSound | null)[] {
  let k = 0
  return paragraphs.map((text) => {
    if (!text.trim() || HEADING.test(text)) return null
    const a = analysed[k]
    if (a && a.text.trim() === text.trim()) {
      k++
      return a
    }
    return null
  })
}

const rhythmKey = new PluginKey<DecorationSet>("frank-rhythm")

function stressMarks(stresses: string): string {
  return stresses.replace(/1/g, "●").replace(/2/g, "•").replace(/0/g, "·")
}

function buildDecorations(doc: PMNode, analysed: LyricLineSound[] | null): DecorationSet {
  const paragraphs: { node: PMNode; pos: number }[] = []
  doc.forEach((node, pos) => paragraphs.push({ node, pos }))
  const matched = analysed ? matchLines(paragraphs.map((p) => p.node.textContent), analysed) : []
  const decos: Decoration[] = []
  paragraphs.forEach(({ node, pos }, i) => {
    const text = node.textContent
    const section = HEADING.exec(text)
    if (section) {
      const raw = section[1].toLowerCase().replace("-", "")
      const kind = raw === "hook" || raw === "refrain" ? "chorus" : raw
      decos.push(Decoration.node(pos, pos + node.nodeSize, { "data-section-heading": "true", "data-section-kind": kind }))
    }
    const line = matched[i]
    if (!line) return
    if (line.rhyme_group !== null) {
      decos.push(Decoration.node(pos, pos + node.nodeSize, { "data-rhyme": String(line.rhyme_group % 6) }))
    }
    // strong and soft syllables, word by word
    let from = 0
    for (const w of line.words) {
      const at = text.indexOf(w.text, from)
      if (at < 0) continue
      from = at + w.text.length
      const end = pos + 1 + from
      decos.push(Decoration.widget(end, () => {
        const span = document.createElement("span")
        span.className = "frank-stress"
        span.setAttribute("aria-hidden", "true")
        span.textContent = stressMarks(w.stresses)
        return span
      }, { side: 1, key: `s${i}-${at}-${w.stresses}` }))
    }
    decos.push(Decoration.widget(pos + node.nodeSize - 1, () => {
      const span = document.createElement("span")
      span.className = "frank-beats"
      span.textContent = `${line.syllables} beat${line.syllables === 1 ? "" : "s"}${line.guessed ? " (about)" : ""}`
      return span
    }, { side: 1, key: `b${i}-${line.syllables}` }))
  })
  return DecorationSet.create(doc, decos)
}

function rhythmExtension(get: () => LyricLineSound[] | null) {
  return Extension.create({
    name: "frankRhythm",
    addProseMirrorPlugins() {
      return [
        new Plugin<DecorationSet>({
          key: rhythmKey,
          state: {
            init: (_, state) => buildDecorations(state.doc, get()),
            apply: (tr, old, _o, state) => (tr.docChanged || tr.getMeta(rhythmKey) ? buildDecorations(state.doc, get()) : old),
          },
          props: { decorations: (state) => rhythmKey.getState(state) },
        }),
      ]
    },
  })
}

export function LyricsEditor({ projectId, initialContent, onSelectionChange, onContentChange, onVersionSaved }: LyricsEditorProps) {
  const [content, setContent] = useState(initialContent)
  const [saveState, setSaveState] = useState<SaveState>("idle")
  const [showRhythm, setShowRhythm] = useState(false)
  const [notes, setNotes] = useState<string[]>([])
  const [rhymes, setRhymes] = useState<RhymeSuggestions | null>(null)
  const analysedRef = useRef<LyricLineSound[] | null>(null)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const analyseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSavedRef = useRef(initialContent)
  const showRef = useRef(false)
  const { updateActiveState } = useProjectStore()

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

  const refreshRhythm = useCallback(
    (editor: Editor, text: string) => {
      if (!showRef.current || !text.trim()) {
        analysedRef.current = null
        editor.view.dispatch(editor.state.tr.setMeta(rhythmKey, true))
        return
      }
      analyseLyrics(projectId, text)
        .then((res) => {
          analysedRef.current = res.lines
          setNotes(res.notes)
          if (!editor.isDestroyed) editor.view.dispatch(editor.state.tr.setMeta(rhythmKey, true))
        })
        .catch(() => setNotes([]))
    },
    [projectId],
  )

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({ heading: false, bulletList: false, orderedList: false, blockquote: false, codeBlock: false, horizontalRule: false }),
      rhythmExtension(() => analysedRef.current),
    ],
    content: textToDoc(initialContent),
    editorProps: {
      attributes: {
        class: "frank-lyrics min-h-[420px] w-full font-written text-xl leading-[1.6] text-on-surface focus-visible:outline-none",
        "aria-label": "Your words",
        spellcheck: "true",
        role: "textbox",
        "aria-multiline": "true",
      },
    },
    onUpdate: ({ editor: ed }) => {
      const text = docToText(ed.state.doc)
      setContent(text)
      onContentChange?.(text)
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      saveTimerRef.current = setTimeout(() => void doSave(text), AUTOSAVE_DELAY_MS)
      if (analyseTimerRef.current) clearTimeout(analyseTimerRef.current)
      analyseTimerRef.current = setTimeout(() => refreshRhythm(ed, text), ANALYSE_DELAY_MS)
    },
    onSelectionUpdate: ({ editor: ed }) => {
      const { from, to } = ed.state.selection
      const selected = ed.state.doc.textBetween(from, to, "\n")
      if (selected.trim()) onSelectionChange?.(selected)
      const word = selected.trim()
      if (/^[A-Za-z']{2,30}$/.test(word)) {
        findRhymes(projectId, word).then(setRhymes).catch(() => setRhymes(null))
      } else {
        setRhymes(null)
      }
    },
  })

  // Keep content in sync if the active version changes externally (e.g. restore)
  useEffect(() => {
    if (!editor || initialContent === docToText(editor.state.doc)) return
    editor.commands.setContent(textToDoc(initialContent), false)
    setContent(initialContent)
    lastSavedRef.current = initialContent
  }, [initialContent, editor])

  useEffect(() => {
    showRef.current = showRhythm
    if (editor) refreshRhythm(editor, docToText(editor.state.doc))
  }, [showRhythm, editor, refreshRhythm])

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
      if (analyseTimerRef.current) clearTimeout(analyseTimerRef.current)
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
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-line/40 pb-3">
        <div className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className={`h-2 w-2 rounded-full ${saveState === "failed" ? "bg-problem" : saveState === "saving" ? "bg-caution" : "bg-tertiary shadow-[0_0_6px_rgba(84,221,252,0.8)]"}`}
          />
          <p role="status" aria-live="polite" className={saveState === "failed" ? "text-sm text-problem" : "text-sm text-on-surface-variant"}>
            {status || "Saved just now"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-code uppercase tracking-wider text-on-surface-variant/60">Plain Text Mode</span>
          <button
            type="button"
            onClick={() => setShowRhythm((v) => !v)}
            aria-pressed={showRhythm}
            className="flex min-h-11 items-center rounded-lg bg-surface-container px-3 py-1 text-label-md text-on-surface-variant hover:bg-surface-high hover:text-on-surface"
          >
            {showRhythm ? "Hide the rhythm" : "Show the rhythm"}
          </button>
        </div>
      </div>
      <div className="relative" data-rhythm={showRhythm ? "on" : "off"}>
        {editor && !content && (
          <p aria-hidden className="pointer-events-none absolute left-0 top-0 whitespace-pre-line text-base leading-relaxed text-on-surface-variant/50">
            {"Start writing.\n\nA line, a feeling, a whole chorus. Mark a section by giving it its own line: Verse, Chorus, Bridge."}
          </p>
        )}
        <EditorContent editor={editor} />
      </div>
      {showRhythm && notes.length > 0 && (
        <ul className="mt-4 space-y-1 text-sm text-ink-2" aria-label="What Frank noticed about the rhythm">
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      {rhymes && (rhymes.rhymes.length > 0 || rhymes.near.length > 0) && (
        <div className="mt-4 rounded-lg border border-line bg-surface-low p-3 text-sm" aria-live="polite">
          <p className="text-on-surface-variant">
            Words that rhyme with <span className="font-written text-on-surface">{rhymes.word}</span>
          </p>
          <p className="mt-1 text-on-surface">{rhymes.rhymes.slice(0, 10).join(", ")}</p>
          {rhymes.near.length > 0 && (
            <p className="mt-2 text-on-surface-variant/70">
              Nearly rhyme: <span className="text-on-surface-variant">{rhymes.near.slice(0, 8).join(", ")}</span>
            </p>
          )}
        </div>
      )}
    </div>
  )
}
