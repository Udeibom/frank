"use client"

import { Sparkles } from "lucide-react"

export default function FeelLabPage() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-8 py-16">
      <div className="flex flex-col items-center gap-4 text-center max-w-sm">
        <div className="rounded-full bg-primary/10 p-5">
          <Sparkles className="h-8 w-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground">Feel Lab</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          This is where your song finds its feeling. You don&apos;t need to know
          what kind of music you want — just describe how it should feel, and
          Frank will find the direction with you.
        </p>
        <p className="text-xs text-muted-foreground/40 mt-4">Coming in Spec 03</p>
      </div>
    </div>
  )
}
