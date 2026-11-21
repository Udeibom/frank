"use client"

/**
 * The one-time notice (frankenstein spec 14, requirement 9.1): to listen to a mix or look at a picture, Frank sends
 * a short clip or the picture to Google's Gemini. Shown once per computer. In the EEA, Switzerland and the UK
 * nothing is sent at all (Google's terms), so the notice says that instead.
 */

import { useEffect, useState } from "react"
import { region } from "@/lib/api/client"

const KEY = "frank.gemini-notice-seen"
const BLOCKED = new Set(
  "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE IS LI NO CH GB".split(" "),
)

export function GeminiNotice({ what }: { what: string }) {
  const [state, setState] = useState<"hidden" | "show" | "blocked">("hidden")

  useEffect(() => {
    if (window.localStorage.getItem(KEY) === "yes") return
    void region().then((c) => setState(c && !BLOCKED.has(c) ? "show" : c ? "blocked" : "hidden"))
  }, [])

  if (state === "hidden") return null
  return (
    <p className="flex flex-wrap items-center gap-2 text-xs text-ink-3" role="note">
      {state === "show"
        ? `To hear and see like a person would, Frank sends ${what} to Google's Gemini. Nothing else about you goes with it.`
        : "Where you are, Frank keeps everything to its own measurements: nothing is sent to Google."}
      <button
        onClick={() => {
          window.localStorage.setItem(KEY, "yes")
          setState("hidden")
        }}
        className="underline underline-offset-2 hover:text-ink"
      >
        Got it
      </button>
    </p>
  )
}
