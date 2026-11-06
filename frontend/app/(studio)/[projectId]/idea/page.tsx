"use client"

import { PenLine } from "lucide-react"

export default function IdeaRoomPage() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-8 py-16">
      <div className="flex flex-col items-center gap-4 text-center max-w-sm">
        <div className="rounded-full bg-primary/10 p-5">
          <PenLine className="h-8 w-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground">Idea Room</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          This is where your song starts. Write your lyrics here — every word,
          every version, saved as you go. Frank will help you shape them when
          you&apos;re ready.
        </p>
        <p className="text-xs text-muted-foreground/40 mt-4">Coming in Spec 02</p>
      </div>
    </div>
  )
}
