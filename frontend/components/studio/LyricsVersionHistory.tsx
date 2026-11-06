"use client"

/**
 * LyricsVersionHistory — flip through drafts like pages in a notebook.
 * Every saved version is here. Nothing is ever lost. The user can preview,
 * restore, and label any version.
 */

import { useState } from "react"
import type { LyricsVersion } from "@/types/project"
import { updateLyricsLabel } from "@/lib/api/lyrics"
import { History, RotateCcw, X, Tag } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface LyricsVersionHistoryProps {
  versions: LyricsVersion[]
  activeVersionId: string | null
  onRestore: (version: LyricsVersion) => void
  onClose: () => void
  onLabelUpdated: (versionId: string, label: string) => void
}

function firstLine(content: string): string {
  const line = content.split("\n").find((l) => l.trim())
  return line?.trim() || "Empty draft"
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

export function LyricsVersionHistory({
  versions,
  activeVersionId,
  onRestore,
  onClose,
  onLabelUpdated,
}: LyricsVersionHistoryProps) {
  const [previewId, setPreviewId] = useState<string | null>(null)
  const [editingLabelId, setEditingLabelId] = useState<string | null>(null)
  const [labelDraft, setLabelDraft] = useState("")

  const previewVersion = versions.find((v) => v.id === previewId)

  async function saveLabel(version: LyricsVersion) {
    setEditingLabelId(null)
    const label = labelDraft.trim()
    if (!label || label === version.label) return
    // Optimistically show the new label, revert if the save fails
    onLabelUpdated(version.id, label)
    try {
      await updateLyricsLabel(version.project_id, version.id, label)
    } catch {
      onLabelUpdated(version.id, version.label ?? "")
    }
  }

  return (
    <div className="flex h-full w-72 flex-col border-l border-border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Your drafts</span>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close drafts">
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Preview overlay */}
      {previewVersion && (
        <div className="border-b border-border bg-background/50 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {formatTime(previewVersion.created_at)}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPreviewId(null)}
              className="h-6 text-xs"
            >
              Close preview
            </Button>
          </div>
          <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap text-xs text-muted-foreground leading-relaxed font-sans">
            {previewVersion.content}
          </pre>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onRestore(previewVersion)}
            className="mt-3 w-full"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Bring this back
          </Button>
        </div>
      )}

      {/* Version list */}
      <div className="flex-1 overflow-y-auto">
        {versions.length === 0 ? (
          <p className="px-4 py-6 text-center text-xs text-muted-foreground/50">
            Your drafts will appear here as you write.
          </p>
        ) : (
          <div className="flex flex-col">
            {versions.map((version) => (
              <div
                key={version.id}
                className={cn(
                  "group border-b border-border/50 px-4 py-3 transition-colors hover:bg-secondary/50",
                  version.id === activeVersionId && "bg-primary/5",
                )}
              >
                <button
                  onClick={() => setPreviewId(version.id)}
                  className="w-full text-left"
                >
                  <p className="truncate text-sm text-foreground">
                    {firstLine(version.content)}
                  </p>
                </button>

                <div className="mt-1 flex items-center justify-between">
                  {editingLabelId === version.id ? (
                    <input
                      autoFocus
                      value={labelDraft}
                      onChange={(e) => setLabelDraft(e.target.value)}
                      onBlur={() => saveLabel(version)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveLabel(version)
                        if (e.key === "Escape") setEditingLabelId(null)
                      }}
                      placeholder="Label this draft"
                      className="w-full bg-transparent text-xs text-primary outline-none"
                    />
                  ) : (
                    <button
                      onClick={() => {
                        setEditingLabelId(version.id)
                        setLabelDraft(version.label ?? "")
                      }}
                      className="flex items-center gap-1 text-xs text-muted-foreground/60 hover:text-primary"
                    >
                      {version.label ? (
                        <>
                          <Tag className="h-3 w-3" />
                          {version.label}
                        </>
                      ) : (
                        <span className="opacity-0 group-hover:opacity-100 transition-opacity">
                          {formatTime(version.created_at)}
                        </span>
                      )}
                    </button>
                  )}
                  {version.id === activeVersionId && (
                    <span className="text-xs text-primary">current</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
