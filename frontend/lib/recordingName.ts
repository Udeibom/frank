/**
 * What a recording is called on screen (core-path spec 15, requirement 5.2). Older songs saved their recordings
 * as "Take 1", "Take 2"; a person with no studio background reads "take" as nothing. They are shown as
 * "Recording 1", "Recording 2", the same as new ones.
 */
export function recordingName(label: string | null | undefined, fallback = "This recording"): string {
  if (!label) return fallback
  const m = /^Take (\d+)$/.exec(label.trim())
  return m ? `Recording ${m[1]}` : label
}
