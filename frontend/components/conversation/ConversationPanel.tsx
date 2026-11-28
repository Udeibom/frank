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
import { useAudio, type Material } from "@/store/audio"
import { speakNote } from "@/lib/api/organs"

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
  words: "border-words",
  feel:  "border-feel",
  music: "border-music",
  voice: "border-voice",
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
  const panelRoom = Boolean(room)

  // Frank reads its notes aloud (frankenstein spec 14, 4.5): off by default, remembered on this computer, and only
  // when nothing else is playing, so it never talks over the song.
  const [speaks, setSpeaks] = useState(false)
  const spoken = useRef<string | null>(null)
  useEffect(() => setSpeaks(window.localStorage.getItem("frank.speaks") === "yes"), [])
  useEffect(() => {
    const last = [...turns].reverse().find((t) => t.role === "assistant" && typeof t.content === "string" && t.content.trim())
    if (!speaks || !projectId || !last || spoken.current === last.id) return
    spoken.current = last.id
    if (useAudio.getState().playing) return
    speakNote(projectId, String(last.content).slice(0, 1200))
      .then((r) => {
        if (r.audio_url && !useAudio.getState().playing) {
          void useAudio.getState().play({ id: `frank-says:${last.id}`, url: r.audio_url, label: "Frank reading its note", material: "words" })
        }
      })
      .catch(() => {})
  }, [turns, speaks, projectId])

  // What Frank knows: the same plain line the Song Strip shows, so the person can see Frank has the song.
  const record = useSongStore((s) => s.record)
  const tried = useDirections((s) => s.directions.some((d) => d.status === "ready"))
  const knows = useMemo(() => buildStripModel(record, tried), [record, tried])

  // Narrow windows start with the panel tucked away so it never squeezes the room.
  useEffect(() => {
    if (window.matchMedia("(max-width: 1200px)").matches) setOpen(false)
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

  const lineUser = panelRoom
    ? cn("border-l-2 pl-3 font-written text-base leading-6", rule)
    : cn("border-l-2 pl-3 font-written text-[17px] leading-[25px]", rule)
  const lineFrank = panelRoom
    ? "rounded-lg border-l-2 border-frank/40 bg-surface-high p-3 text-sm font-medium leading-5 text-on-surface"
    : "border-l-2 border-frank/40 pl-3 py-1.5 rounded-r-md bg-frank/[0.04] text-base leading-[21px] font-[500] text-ink"

  return (
    <>
      {/* At 1200px and below the panel opens over the room; this keeps the tab's place in the row. */}
      <div aria-hidden="true" className="hidden w-14 shrink-0 max-[1200px]:block" />
      <aside
        aria-label="Frank"
        className={cn(
          "flex w-[340px] shrink-0 flex-col border-l border-line bg-surface max-[1200px]:fixed max-[1200px]:bottom-0 max-[1200px]:right-0 max-[1200px]:top-16 max-[1200px]:z-40 max-[1200px]:w-full max-[1200px]:max-w-[420px] max-[1200px]:shadow-l3",
          panelRoom && "bg-surface-low",
        )}
      >
        <div className={panelRoom ? "flex items-center justify-between gap-3 bg-surface-high px-4 py-3" : "flex items-start justify-between gap-3 border-b border-line px-4 py-3"}>
          <div className="min-w-0 flex items-center gap-2">
            <span
              className={panelRoom ? "flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-frank text-sm font-bold italic text-on-primary select-none" : "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-sm font-bold italic select-none"}
              style={panelRoom ? undefined : { background: "rgb(var(--frank) / 0.15)", color: "rgb(var(--frank))" }}
              aria-hidden="true"
            >
              f
            </span>
            <div className="min-w-0">
              <h2 className={panelRoom ? "text-label-md text-on-surface" : "text-xs font-semibold uppercase tracking-[0.06em] text-ink-3"}>Frank</h2>
              {!panelRoom && (
                <p className="text-xs text-ink-3 truncate max-w-[180px]">
                  {record && (!projectId || record.project_id === projectId)
                    ? knows.summary
                    : "Reading your song…"}
                </p>
              )}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              onClick={() => {
                const next = !speaks
                setSpeaks(next)
                window.localStorage.setItem("frank.speaks", next ? "yes" : "no")
              }}
              aria-pressed={speaks}
              className={panelRoom ? "min-h-11 rounded-sm px-2 text-on-surface-variant hover:text-on-surface" : "min-h-11 rounded-sm px-2 text-[10px] text-ink-3 hover:text-ink"}
            >
              {speaks ? "Reading aloud" : "Read aloud"}
            </button>
            <button
              onClick={() => setOpen(false)}
              aria-label="Hide the conversation with Frank"
              className={cn("flex min-h-11 min-w-11 items-center justify-center rounded-sm", panelRoom ? "text-on-surface-variant hover:text-on-surface" : "text-ink-3 hover:text-ink")}
            >
              <ChevronsRight className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>
        {panelRoom && (
          <div className="bg-surface-container px-4 py-3">
            <p className="mb-1 text-label-sm font-semibold uppercase tracking-[0.06em] text-frank-text">What Frank knows</p>
            <p className="line-clamp-2 text-sm leading-relaxed text-on-surface-variant">
              {record && (!projectId || record.project_id === projectId)
                ? knows.summary
                : "Reading your song…"}
            </p>
          </div>
        )}

        <div ref={scrollRef} className={cn("overscroll-contain", panelRoom ? "flex-1 overflow-y-auto px-4 py-4" : "flex-1 overflow-y-auto px-4 py-5")} aria-live="polite" aria-relevant="additions">
          {earlier.length > 0 && (
            <div className="mb-5 flex flex-col gap-4" role="group" aria-label="Earlier conversation">
              <p className={panelRoom ? "text-code uppercase tracking-widest text-on-surface-variant" : "text-xs font-semibold uppercase tracking-[0.06em] text-ink-3"}>Earlier</p>
              {earlier.map((t, i) => (
                <p key={`earlier-${i}`} className={t.role === "user" ? lineUser : cn(lineFrank, panelRoom ? "text-on-surface" : "text-ink-2")}>
                  {t.content}
                </p>
              ))}
              <p className={panelRoom ? "border-t border-line pt-3 text-code uppercase tracking-widest text-on-surface-variant" : "border-t border-line pt-3 text-xs font-semibold uppercase tracking-[0.06em] text-ink-3"}>Now</p>
            </div>
          )}
          {turns.length === 0 && !isThinking && earlier.length === 0 ? (
            <p className="px-2 pt-8 text-center text-sm text-ink-2">{emptyText}</p>
          ) : (
            <div className="flex flex-col gap-5">
              {turns.map((turn) => (
                <div key={turn.id} className="flex flex-col gap-2.5">
                  {turn.content && (
                    <div className={turn.role === "user" ? "" : "flex flex-col gap-0.5"}>
                      {turn.role === "assistant" && (
                        <span className="flex items-center gap-1.5 mb-0.5" aria-hidden="true">
                          <span
                            className="flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold italic select-none"
                            style={{ background: "rgb(var(--frank) / 0.15)", color: "rgb(var(--frank))" }}
                          >
                            f
                          </span>
                          <span className="text-[9px] font-semibold uppercase tracking-[0.1em] text-ink-3">Frank</span>
                        </span>
                      )}
                      <p className={turn.role === "user" ? lineUser : lineFrank}>{turn.content}</p>
                    </div>
                  )}
                  {turn.actionBlock}
                </div>
              ))}
              {isThinking && (
                <div className="flex flex-col gap-0.5">
                  <span className="flex items-center gap-1.5 mb-0.5" aria-hidden="true">
                    <span
                      className="flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold italic select-none"
                      style={{ background: "rgb(var(--frank) / 0.15)", color: "rgb(var(--frank))" }}
                    >
                      f
                    </span>
                    <span className="text-[9px] font-semibold uppercase tracking-[0.1em] text-ink-3">Frank</span>
                  </span>
                  <div className="dot-pulse flex gap-1.5 py-2 pl-3" role="status" aria-label="Frank is thinking">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className={cn("safe-bottom", panelRoom ? "border-t border-line bg-surface-container p-4" : "border-t border-line p-4")}>
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
              rows={2}
              className={panelRoom ? "max-h-32 min-h-[56px] flex-1 resize-none rounded-lg bg-surface-low px-3 py-3 text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-1 focus:ring-frank/40 transition-shadow" : "max-h-32 min-h-[56px] flex-1 resize-none rounded-xl bg-raised px-3 py-3 text-base text-ink placeholder:text-ink-3 focus:outline-none focus:ring-1 focus:ring-frank/40 transition-shadow"}
              aria-label="Message to Frank"
            />
            <button
              type="submit"
              disabled={!input.trim() || isThinking}
              aria-label="Send message"
              className={panelRoom ? "flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-frank text-on-primary transition-all hover:bg-frank/90 hover:scale-105 disabled:bg-surface-high disabled:text-on-surface-variant disabled:scale-100" : "flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-frank text-ground transition-all hover:bg-frank/90 hover:scale-105 disabled:bg-raised disabled:text-ink-3 disabled:scale-100"}
            >
              <Send className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </form>
      </aside>
    </>
  )
}
