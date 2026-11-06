"use client"

/**
 * ConversationPanel — the always-present space where the user talks to Frank.
 * Reused across every layer. The parent supplies how to send a message and
 * how to render any special action blocks (like lyric suggestions).
 */

import { useRef, useEffect, useState, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { Send, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

export interface ChatTurn {
  id: string
  role: "user" | "assistant"
  content: string
  // Optional custom block rendered under an assistant message (e.g. a lyric suggestion)
  actionBlock?: ReactNode
}

interface ConversationPanelProps {
  turns: ChatTurn[]
  onSend: (message: string) => void
  isThinking: boolean
  placeholder?: string
  // Optional slot above the input (e.g. the voice memo button)
  inputAccessory?: ReactNode
}

export function ConversationPanel({
  turns,
  onSend,
  isThinking,
  placeholder = "Talk to Frank…",
  inputAccessory,
}: ConversationPanelProps) {
  const [input, setInput] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to the newest message
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    })
  }, [turns, isThinking])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || isThinking) return
    onSend(text)
    setInput("")
  }

  return (
    <div className="flex h-full w-80 flex-col border-l border-border bg-card">
      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-5">
        {turns.length === 0 && !isThinking ? (
          <div className="flex h-full items-center justify-center px-4 text-center">
            <p className="text-sm text-muted-foreground/50 leading-relaxed">
              Stuck on a line? Need a rhyme? Want a second pair of ears?
              <br />
              Frank is here.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {turns.map((turn) => (
              <div
                key={turn.id}
                className={cn(
                  "flex flex-col gap-2",
                  turn.role === "user" ? "items-end" : "items-start",
                )}
              >
                <div
                  className={cn(
                    "max-w-[90%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
                    turn.role === "user"
                      ? "bg-primary/15 text-foreground"
                      : "bg-secondary text-foreground",
                  )}
                >
                  {turn.content}
                </div>
                {turn.actionBlock}
              </div>
            ))}

            {isThinking && (
              <div className="flex items-start">
                <div className="rounded-2xl bg-secondary px-3.5 py-2.5">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t border-border p-3">
        {inputAccessory && <div className="mb-2">{inputAccessory}</div>}
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
            className="flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring max-h-32"
            aria-label="Message to Frank"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || isThinking}
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </form>
    </div>
  )
}
