"use client"

/**
 * ConversationPanel: Frank's panel, a margin beside whatever room the user is in (design-and-ui.md).
 * Not a chat window: no bubbles, no avatar. Frank's lines are plain text; the user's own lines are set in the
 * written face with a rule in the room's colour. It keeps the same props as before, so every room gets the
 * new panel without changing how it talks to Frank.
 *
 * - "What Frank knows" is pinned at the top, read from the shared song record.
 * - Anything Frank does that changes the song arrives as an `actionBlock` (a ChangeLine), under his message.
 * - 340px; hides to a 56px tab; at 1100px and below it opens over the stage instead of squeezing it.
 */

import { useRef, useEffect, useMemo, useState, type ReactNode } from "react"
import { ChevronsRight, MessageCircle, Send } from "lucide-react"
import { cn } from "@/lib/utils"
import { getRoomHistory, type StoredTurn } from "@/lib/api/conversation"
import { useSongStore } from "@/store/song"
import { useDirections } from "@/store/directions"
import { buildStripModel } from "@/lib/songShape"
import type { Material } from "@/store/audio"

export interface ChatTurn {
  id: string
  role: "user" | "assistant"
  content: string
  // Optional custom block rendered under an assistant message (e.g. a lyric suggestion or a change line)
  actionBlock?: ReactNode
}

interface ConversationPanelProps {
  turns: ChatTurn[]
  onSend: (message: string) => void
  isThinking: boolean
  placeholder?: string
  // Optional slot above the input (e.g. the voice memo button)
  inputAccessory?: ReactNode
  // Shown before the first message. Each room should pass its own.
  emptyText?: string
  // When given, what was said in this room before (stored on the server) is shown above this session.
  projectId?: string
  room?: "idea" | "feel" | "beat" | "voice" | "mix" | "export"
  /** The colour of the rule beside the user's own lines: the material this room works on. */
  material?: Material
}

const RULE: Record<Material, string> = {
  words: "border-words text-words",
  feel: "border-feel text-words",
  music: "border-music text-words",
  voice: "border-voice text-words",
}

const ROOM_MATERIAL: Record<string, Material> = { idea: "words", feel: "feel", beat: "music", voice: "voice", mix: "music", export: "music" }

export function ConversationPanel({
  turns,
  onSend,
  isThinking,
  placeholder = "Talk to Frank…",
  inputAccessory,
  emptyText = "Frank is here.",
  projectId,
  room,
  material,
}: ConversationPanelProps) {
  const [input, setInput] = useState("")
  const [earlier, setEarlier] = useState<StoredTurn[]>([])
  const [open, setOpen] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)
  const rule = RULE[material ?? (room ? ROOM_MATERIAL[room] : "words")]

  // What Frank knows: the same plain line the Song Strip shows, so the person can see Frank has the song.
  const record = useSongStore((s) => s.record)
  const tried = useDirections((s) => s.directions.some((d) => d.status === "ready"))
  const knows = useMemo(() => buildStripModel(record, tried), [record, tried])

  // Narrow windows start with the panel tucked away so it never squeezes the room.
  useEffect(() => {
    if (window.matchMedia("(max-width: 1100px)").matches) setOpen(false)
  }, [])

  // The stored conversation from earlier visits. Loaded once per room; a failure just means nothing is shown.
  useEffect(() => {
    if (!projectId || !room) return
    let alive = true
    getRoomHistory(projectId, room)
      .then((h) => alive && setEarlier(h))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [projectId, room])

  // Keep the newest line in view
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [turns, isThinking, open])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || isThinking) return
    onSend(text)
    setInput("")
  }

  if (!open) {
    return (
      <aside aria-label="Frank" className="flex w-14 shrink-0 flex-col items-center border-l border-line bg-surface py-3">
        <button
          onClick={() => setOpen(true)}
          aria-label="Open the conversation with Frank"
          className="flex flex-col items-center gap-1 rounded-md px-1 py-2 text-xs text-ink-2 hover:text-ink"
        >
          <MessageCircle className="h-5 w-5" aria-hidden="true" />
          Frank
        </button>
      </aside>
    )
  }

  const lineUser = cn("border-l-2 pl-3 font-written text-[17px] leading-[25px]", rule)
  const lineFrank = "text-base text-ink"

  return (
    <>
      {/* At 1100px and below the panel opens over the room; this keeps the tab's place in the row. */}
      <div aria-hidden="true" className="hidden w-14 shrink-0 max-[1100px]:block" />
      <aside
        aria-label="Frank"
        className="flex w-[340px] shrink-0 flex-col border-l border-line bg-surface max-[1100px]:fixed max-[1100px]:bottom-0 max-[1100px]:right-0 max-[1100px]:top-24 max-[1100px]:z-30 max-[1100px]:shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h2 className="mb-1 text-xs font-semibold uppercase tracking-[0.06em] text-ink-3">What Frank knows</h2>
            <p className="text-sm text-ink-2">{record && (!projectId || record.project_id === projectId) ? knows.summary : "Reading your song…"}</p>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Hide the conversation with Frank"
            className="shrink-0 rounded-sm p-1 text-ink-3 hover:text-ink"
          >
            <ChevronsRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-5" aria-live="polite" aria-relevant="additions">
          {earlier.length > 0 && (
            <div className="mb-5 flex flex-col gap-4" role="group" aria-label="Earlier conversation">
              <p className="text-xs font-semibold uppercase tracking-[0.06em] text-ink-3">Earlier</p>
              {earlier.map((t, i) => (
                <p key={`earlier-${i}`} className={t.role === "user" ? lineUser : cn(lineFrank, "text-ink-2")}>
                  {t.content}
                </p>
              ))}
              <p className="border-t border-line pt-3 text-xs font-semibold uppercase tracking-[0.06em] text-ink-3">Now</p>
            </div>
          )}
          {turns.length === 0 && !isThinking && earlier.length === 0 ? (
            <p className="px-2 pt-8 text-center text-sm text-ink-2">{emptyText}</p>
          ) : (
            <div className="flex flex-col gap-5">
              {turns.map((turn) => (
                <div key={turn.id} className="flex flex-col gap-2.5">
                  {turn.content && <p className={turn.role === "user" ? lineUser : lineFrank}>{turn.content}</p>}
                  {turn.actionBlock}
                </div>
              ))}
              {isThinking && <p className="text-sm text-ink-3">Frank is thinking…</p>}
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="border-t border-line p-4">
          {inputAccessory && <div className="mb-3">{inputAccessory}</div>}
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleSubmit(e)
                }
              }}
              placeholder={placeholder}
              rows={1}
              className="max-h-32 min-h-[40px] flex-1 resize-none rounded-md bg-raised px-3 py-2.5 text-base text-ink placeholder:text-ink-3"
              aria-label="Message to Frank"
            />
            <button
              type="submit"
              disabled={!input.trim() || isThinking}
              aria-label="Send message"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-raised text-ink transition-colors hover:bg-line disabled:text-ink-3"
            >
              <Send className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </form>
      </aside>
    </>
  )
}
