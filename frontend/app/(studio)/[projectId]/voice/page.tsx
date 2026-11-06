"use client"

import { Mic2 } from "lucide-react"

export default function VoiceRoomPage() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-8 py-16">
      <div className="flex flex-col items-center gap-4 text-center max-w-sm">
        <div className="rounded-full bg-primary/10 p-5">
          <Mic2 className="h-8 w-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground">Voice Room</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          This is where your voice goes in. Record as many takes as you need,
          compare them, and let Frank help you get the best version of your
          performance — no technical knowledge required.
        </p>
        <p className="text-xs text-muted-foreground/40 mt-4">Coming in Spec 05</p>
      </div>
    </div>
  )
}
