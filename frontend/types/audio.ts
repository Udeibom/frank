// ─────────────────────────────────────────────
// Audio types for Frank
// All audio processing happens server-side.
// These types describe data the frontend receives and displays.
// ─────────────────────────────────────────────

export type PlaybackState = "idle" | "loading" | "playing" | "paused"

export interface AudioFile {
  id: string
  url: string
  duration: number | null   // seconds
  waveform: number[] | null // normalised amplitude values 0.0–1.0, for display only
  label: string | null
}

// A single point in the pitch contour of a vocal take.
// Produced by Basic Pitch on the backend, sent to the frontend for display.
export interface PitchPoint {
  time: number        // seconds from start
  note: number        // MIDI note number (0–127)
  confidence: number  // 0.0–1.0
}

// Colour-coded pitch accuracy — derived on the frontend from PitchPoint.confidence
export type PitchAccuracy = "good" | "close" | "off"

export function pitchAccuracy(confidence: number): PitchAccuracy {
  if (confidence >= 0.8) return "good"
  if (confidence >= 0.5) return "close"
  return "off"
}

export interface WaveformData {
  peaks: number[]     // normalised amplitude peaks, one per display pixel bucket
  duration: number    // seconds
  sample_rate: number
}

export interface RecordingState {
  isRecording: boolean
  isPaused: boolean
  durationSeconds: number
  inputLevel: number  // 0.0–1.0, for the level meter
}
