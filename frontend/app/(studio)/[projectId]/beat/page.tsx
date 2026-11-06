"use client"

import { Drum } from "lucide-react"

export default function BeatRoomPage() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-8 py-16">
      <div className="flex flex-col items-center gap-4 text-center max-w-sm">
        <div className="rounded-full bg-primary/10 p-5">
          <Drum className="h-8 w-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground">Beat Room</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          This is where the music behind your voice takes shape. Start from the
          feeling you found, build it up piece by piece, and shape it until it
          moves the way you need it to.
        </p>
        <p className="text-xs text-muted-foreground/40 mt-4">Coming in Spec 04</p>
      </div>
    </div>
  )
}
