"use client"

import { SlidersHorizontal } from "lucide-react"

export default function MixRoomPage() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-8 py-16">
      <div className="flex flex-col items-center gap-4 text-center max-w-sm">
        <div className="rounded-full bg-primary/10 p-5">
          <SlidersHorizontal className="h-8 w-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground">Mix Room</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          This is where everything comes together. Your voice, the music behind
          it — balanced and shaped until it sounds exactly like it should. Just
          tell Frank what feels off and it will adjust.
        </p>
        <p className="text-xs text-muted-foreground/40 mt-4">Coming in Spec 06</p>
      </div>
    </div>
  )
}
