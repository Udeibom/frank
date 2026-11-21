"use client"

/**
 * The headphone check (frankenstein spec 14, requirement 8.4): about 20 seconds. A chime plays in one ear, then
 * the other; the person says where they heard it. Both right means headphones are on and the right way round,
 * so the music won't get into the mic. The answer is remembered on this computer.
 */

import { useRef, useState } from "react"
import { SessionPlayer } from "@/lib/audio/sessionPlayer"
import { useAudio } from "@/store/audio"

type Heard = "left" | "right" | "both"

const KEY = "frank.headphones-checked"

export function headphonesChecked(): boolean {
  return typeof window !== "undefined" && window.localStorage.getItem(KEY) === "yes"
}

interface HeadphoneCheckProps {
  onResult: (wearing: boolean) => void
  onClose: () => void
}

export function HeadphoneCheck({ onResult, onClose }: HeadphoneCheckProps) {
  const player = useRef(new SessionPlayer())
  const pause = useAudio((s) => s.pause)
  const [step, setStep] = useState<0 | 1 | 2>(0)
  const [answers, setAnswers] = useState<Heard[]>([])
  const [verdict, setVerdict] = useState<string | null>(null)
  const sides: (-1 | 1)[] = [-1, 1]

  async function playStep(i: 0 | 1) {
    pause()
    await player.current.sideChime(sides[i])
  }

  function answer(h: Heard) {
    const next = [...answers, h]
    setAnswers(next)
    if (step === 0) {
      setStep(1)
      void playStep(1)
      return
    }
    setStep(2)
    const ok = next[0] === "left" && next[1] === "right"
    const swapped = next[0] === "right" && next[1] === "left"
    const speakers = next.every((x) => x === "both")
    if (ok) {
      window.localStorage.setItem(KEY, "yes")
      setVerdict("Your headphones are on and the right way round. The music won't get into your mic.")
    } else if (swapped) {
      setVerdict("Your headphones are on, just the wrong way round. Swap them over; it won't affect the recording.")
    } else if (speakers) {
      setVerdict("It sounds like this is coming from speakers, so the music may get into your mic. That's fine: I can take it out afterwards.")
    } else {
      setVerdict("I couldn't tell for sure. If you're wearing headphones, you're all set.")
    }
    onResult(ok || swapped)
  }

  return (
    <section aria-label="Headphone check" className="rounded-md border border-line bg-surface p-4 text-base">
      {step < 2 ? (
        <>
          <p className="text-ink">
            {step === 0
              ? "Put your headphones on. I'll play a short chime. Where did you hear it?"
              : "And this one?"}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {answers.length === step && (
              <button onClick={() => void playStep(step === 0 ? 0 : 1)} className="rounded-md border border-line bg-raised px-3 py-1.5 text-ink hover:border-ink-3">
                {step === 0 ? "Play the chime" : "Play it again"}
              </button>
            )}
            {(["left", "right", "both"] as Heard[]).map((h) => (
              <button key={h} onClick={() => answer(h)} className="rounded-md border border-line px-3 py-1.5 text-ink-2 hover:text-ink">
                {h === "left" ? "Left ear" : h === "right" ? "Right ear" : "Both / speakers"}
              </button>
            ))}
          </div>
        </>
      ) : (
        <p className="text-ink" role="status">
          {verdict}
        </p>
      )}
      <button onClick={onClose} className="mt-3 text-sm text-ink-2 hover:text-ink">
        {step === 2 ? "Done" : "Skip"}
      </button>
    </section>
  )
}
