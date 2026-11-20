"use client"

/**
 * ChoiceMenu: a small list of plain choices that opens from a trigger (a grid cell, a section name).
 * Keyboard: Enter/Space opens, arrow keys move, Escape closes and returns focus to the trigger.
 * One pattern everywhere a thing on the stage offers "what can I do with this".
 */

import { useEffect, useRef, useState, type ReactNode } from "react"
import { cn } from "@/lib/utils"

export interface Choice {
  label: string
  onSelect: () => void
  /** A quieter line under the label. */
  hint?: string
  disabled?: boolean
}

interface ChoiceMenuProps {
  /** What the menu is about, for screen readers: "Bass in the first verse". */
  label: string
  choices: Choice[]
  trigger: (props: {
    open: boolean
    toggle: () => void
    ref: (el: HTMLButtonElement | null) => void
    "aria-haspopup": "menu"
    "aria-expanded": boolean
  }) => ReactNode
  align?: "start" | "end"
  className?: string
}

export function ChoiceMenu({ label, choices, trigger, align = "start", className }: ChoiceMenuProps) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) return
    const first = menuRef.current?.querySelector<HTMLButtonElement>("button:not(:disabled)")
    first?.focus()
    const away = (e: MouseEvent) => {
      const t = e.target as Node
      if (!menuRef.current?.contains(t) && !triggerRef.current?.contains(t)) setOpen(false)
    }
    document.addEventListener("mousedown", away)
    return () => document.removeEventListener("mousedown", away)
  }, [open])

  function close(returnFocus = true) {
    setOpen(false)
    if (returnFocus) triggerRef.current?.focus()
  }

  function onKey(e: React.KeyboardEvent) {
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [])
    const at = items.indexOf(document.activeElement as HTMLButtonElement)
    if (e.key === "Escape") {
      e.preventDefault()
      e.stopPropagation()
      close()
    } else if (e.key === "ArrowDown") {
      e.preventDefault()
      items[(at + 1) % items.length]?.focus()
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      items[(at - 1 + items.length) % items.length]?.focus()
    } else if (e.key === "Tab") {
      close(false)
    }
  }

  return (
    <div className={cn("relative", className)}>
      {trigger({
        open,
        toggle: () => setOpen((o) => !o),
        ref: (el) => {
          triggerRef.current = el
        },
        "aria-haspopup": "menu",
        "aria-expanded": open,
      })}
      {open && (
        <div
          ref={menuRef}
          role="menu"
          aria-label={label}
          onKeyDown={onKey}
          className={cn(
            "absolute top-full z-30 mt-1 w-56 rounded-md border border-line bg-surface p-1 shadow-xl",
            align === "end" ? "right-0" : "left-0",
          )}
        >
          <p className="px-3 pb-1 pt-1.5 text-xs text-ink-3">{label}</p>
          {choices.map((c) => (
            <button
              key={c.label}
              role="menuitem"
              disabled={c.disabled}
              onClick={() => {
                close()
                c.onSelect()
              }}
              className="flex w-full flex-col rounded-sm px-3 py-2 text-left text-base text-ink hover:bg-raised focus-visible:bg-raised disabled:text-ink-3"
            >
              {c.label}
              {c.hint && <span className="text-sm text-ink-2">{c.hint}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
