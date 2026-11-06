"use client"

import { Download } from "lucide-react"

export default function ExportRoomPage() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-8 py-16">
      <div className="flex flex-col items-center gap-4 text-center max-w-sm">
        <div className="rounded-full bg-primary/10 p-5">
          <Download className="h-8 w-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground">Export</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          This is the finish line. Take one last listen, optionally make it
          sound radio-ready, then download your song as an MP3. It&apos;s yours.
        </p>
        <p className="text-xs text-muted-foreground/40 mt-4">Coming in Spec 07</p>
      </div>
    </div>
  )
}
