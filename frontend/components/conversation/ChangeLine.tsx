"use client"

/**
 * ChangeLine: the visible record of something Frank did ("Direction 2 is ready"), with what the person can do
 * about it. Every action Frank takes is one of these, so the changes are never hidden inside a sentence.
 */

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"
import type { Material } from "@/store/audio"

const DOT: Record<Material, string> = {
  words: "bg-words",
  feel: "bg-feel",
  music: "bg-music",
  voice: "bg-voice",
}

interface ChangeLineProps {
  material: Material
  children: ReactNode
  actions?: { label: string; onClick: () => void; ariaLabel?: string }[]
  className?: string
}

export function ChangeLine({ material, children, actions = [], className }: ChangeLineProps) {
  return (
    <div className={cn("flex items-center gap-2.5 rounded-md bg-raised px-3 py-2 text-sm text-ink-2", className)}>
      <span aria-hidden="true" className={cn("h-2 w-2 shrink-0 rounded-[2px]", DOT[material])} />
      <span className="min-w-0 flex-1">{children}</span>
      {actions.map((a) => (
        <button
          key={a.label}
          onClick={a.onClick}
          aria-label={a.ariaLabel}
          className="shrink-0 rounded-sm font-medium text-ink underline underline-offset-4 hover:text-frank"
        >
          {a.label}
        </button>
      ))}
    </div>
  )
}
