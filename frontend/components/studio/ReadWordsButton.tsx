"use client"

/**
 * ReadWordsButton: asks Frank to read the lyrics for how they feel and how they are laid out.
 *
 * Frank answers in the conversation with what it heard, and asks at most one question when it
 * really is not sure. It only reads; it never rewrites a word (start-from-any-input spec 02, req. 2).
 *
 * The button stays on screen while Frank works (disabled and marked busy) so keyboard focus is not
 * lost, and progress is announced through a live region that is always present.
 */

import { useState } from "react"
import { BookOpen, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ApiError } from "@/lib/api/client"
import { readWords } from "@/lib/api/intake"
import { useProjectStore } from "@/store/project"

interface ReadWordsButtonProps {
  projectId: string
  /** The words as they are on screen right now. */
  getWords: () => string
  /** Anything Frank wants to say in the conversation. */
  onSay: (message: string) => void
  /** "stage": a real control on the room's stage. "chat": the compact link above the conversation input. */
  appearance?: "chat" | "stage"
}

const MIN_LINES = 2

/** Statuses whose message comes from Frank's own handlers and is already plain: busy, too big, couldn't read. */
const FRANKS_OWN_STATUSES = [409, 413, 502]

function lineCount(text: string): number {
  return text.split("\n").filter((l) => l.trim()).length
}

/** The honest reason, in Frank's voice. A dropped connection is never presented as the writer's problem. */
function explain(err: unknown): string {
  if (err instanceof ApiError) {
    if (FRANKS_OWN_STATUSES.includes(err.status) && err.message) return err.message
    if (err.status === 422) {
      return "Your song is longer than I can read in one go. Could you try just a part of it?"
    }
  }
  return "I lost the connection for a moment, so I couldn't read your words. They're safe. Want to try again?"
}

export function ReadWordsButton({ projectId, getWords, onSay, appearance = "chat" }: ReadWordsButtonProps) {
  const [working, setWorking] = useState(false)
  const refresh = useProjectStore((s) => s.refresh)

  async function handleClick() {
    const words = getWords()
    if (lineCount(words) < MIN_LINES) {
      onSay("Write a few lines first, then I'll tell you what I hear in them.")
      return
    }
    setWorking(true)
    try {
      const result = await readWords(projectId, words)
      onSay(result.message)
      // The song now knows something new about its feeling: let the rest of the studio know.
      refresh(projectId).catch(() => {})
    } catch (err) {
      onSay(explain(err))
    } finally {
      setWorking(false)
    }
  }

  return (
    <div className="flex flex-col">
      <Button
        variant={appearance === "stage" ? "outline" : "ghost"}
        size="sm"
        onClick={handleClick}
        disabled={working}
        aria-busy={working}
        className={appearance === "stage" ? "h-11 rounded-lg border border-frank bg-frank px-5 text-label-md font-semibold text-on-primary shadow-[0_0_16px_rgba(245,158,11,0.2)] hover:bg-frank-shade" : "w-full justify-start text-muted-foreground"}
      >
        {working ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <BookOpen className="h-4 w-4" aria-hidden="true" />
        )}
        Read my words
      </Button>
      <p role="status" aria-live="polite" className={appearance === "stage" ? "sr-only" : "px-3 text-xs text-muted-foreground"}>
        {working ? "Reading your words… this usually takes a few seconds." : ""}
      </p>
    </div>
  )
}
