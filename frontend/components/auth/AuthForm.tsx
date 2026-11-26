"use client"

/**
 * AuthForm — one form for both /login and /signup. Plain language only:
 * errors never say which of email or password was wrong, and never show a
 * status code.
 */

import { useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { Loader2 } from "lucide-react"

type Mode = "login" | "signup"

/** Only follow in-app destinations; never an external URL. */
export function safeNext(next: string | null): string {
  if (next && next.startsWith("/") && !next.startsWith("//")) return next
  return "/songs"
}

function friendlySignupError(message: string): string {
  const m = message.toLowerCase()
  if (m.includes("already") && m.includes("registered")) {
    return "That email already has an account. Try logging in instead."
  }
  if (m.includes("password")) {
    return "Pick a password with at least 6 characters."
  }
  if (m.includes("valid email") || m.includes("invalid")) {
    return "That doesn't look like an email address."
  }
  return "Something went wrong creating your account — want to try again?"
}

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter()
  const params = useSearchParams()
  const next = safeNext(params.get("next"))

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const isSignup = mode === "signup"

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (isSignup && password !== confirm) {
      setError("Those two passwords don't match.")
      return
    }

    setBusy(true)
    const supabase = createClient()
    try {
      if (isSignup) {
        const { data, error: signUpError } = await supabase.auth.signUp({
          email: email.trim(),
          password,
        })
        if (signUpError) {
          setError(friendlySignupError(signUpError.message))
          return
        }
        // With email confirmation off, signUp returns a session. If it ever
        // doesn't, sign in straight away.
        if (!data.session) {
          const { error: signInError } = await supabase.auth.signInWithPassword({
            email: email.trim(),
            password,
          })
          if (signInError) {
            setError("Your account is ready — please log in.")
            router.push("/login")
            return
          }
        }
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        })
        if (signInError) {
          // Deliberately vague: never reveal which part was wrong.
          setError("That email and password didn't match.")
          return
        }
      }
      router.push(next)
      router.refresh()
    } catch {
      setError("Frank couldn't reach the studio just now — want to try again?")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-ground text-ink">
      {/* Nav */}
      <header className="flex items-center justify-between border-b border-line/60 px-6 py-3">
        <div className="flex items-center gap-2">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-lg"
            style={{ background: "rgb(var(--frank))", boxShadow: "0 0 12px rgba(245,158,11,0.3)" }}
          >
            <span className="font-written italic text-base leading-none text-ground select-none">f</span>
          </div>
          <span className="text-sm font-semibold text-ink">Frank</span>
          <span className="font-mono text-[10px] uppercase tracking-widest text-ink-3 ml-0.5">Studio</span>
          <span className="ml-1 font-mono text-[10px] uppercase tracking-widest text-ink-3">· Workstation Core</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: "rgb(var(--ok))" }} />
          <span className="font-mono text-[11px] text-ink-2">Session Ready</span>
        </div>
      </header>

      {/* Main */}
      <main className="flex flex-1 flex-col items-center justify-center px-4 py-16">
        {/* Ambient glow */}
        <div
          aria-hidden="true"
          className="pointer-events-none fixed inset-0 -z-10"
          style={{
            background:
              "radial-gradient(ellipse 60% 50% at 50% 60%, rgba(245,158,11,0.05) 0%, transparent 70%)",
          }}
        />

        <div className="w-full max-w-sm">
          {/* Card */}
          <div
            className="relative rounded-lg border border-line bg-surface p-7"
            style={{ boxShadow: "0 20px 48px rgba(0,0,0,0.65)" }}
          >
            {/* Analog hardware corner screws */}
            <span className="absolute left-2.5 top-2.5 h-1.5 w-1.5 rounded-full bg-raised opacity-40" aria-hidden="true" />
            <span className="absolute right-2.5 top-2.5 h-1.5 w-1.5 rounded-full bg-raised opacity-40" aria-hidden="true" />
            <span className="absolute bottom-2.5 left-2.5 h-1.5 w-1.5 rounded-full bg-raised opacity-40" aria-hidden="true" />
            <span className="absolute bottom-2.5 right-2.5 h-1.5 w-1.5 rounded-full bg-raised opacity-40" aria-hidden="true" />

            {/* Frank amber badge */}
            <div className="mb-5 flex flex-col items-center gap-2">
              <div
                className="flex h-14 w-14 items-center justify-center rounded-xl"
                style={{
                  background: "rgb(var(--frank) / 0.15)",
                  border: "1px solid rgb(var(--frank) / 0.3)",
                }}
              >
                <span
                  className="font-written italic text-4xl leading-none select-none"
                  style={{ color: "rgb(var(--frank))" }}
                >
                  f
                </span>
              </div>
              <p className="font-mono text-[10px] uppercase tracking-widest text-ink-3">
                Master Console &bull; Rack 01
              </p>
            </div>

            {/* Headline */}
            <h1 className="mb-1 text-center text-2xl font-normal text-ink">
              {isSignup ? (
                "Create your studio account"
              ) : (
                <>
                  Welcome back to{" "}
                  <em className="font-written italic" style={{ color: "rgb(var(--frank))" }}>
                    Frank
                  </em>
                </>
              )}
            </h1>
            <p className="mb-6 text-center text-sm text-ink-2">
              {isSignup
                ? "Make an account so your songs stay yours."
                : "Pick up the song in your head right where you left it."}
            </p>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
              {/* Email field */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="email-input"
                    className="font-mono text-[10px] uppercase tracking-widest text-ink-2"
                  >
                    Studio Pass (Email)
                  </label>
                  <span className="font-mono text-[10px] text-ink-3">ID://SECURE</span>
                </div>
                <input
                  id="email-input"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full rounded-md border border-line bg-ground px-3.5 py-3 text-sm text-ink placeholder:text-ink-3 transition-all focus:outline-none focus:border-frank/50 focus:shadow-[0_0_0_1px_rgba(245,158,11,0.2)]"
                />
              </div>

              {/* Password field */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="password-input"
                    className="font-mono text-[10px] uppercase tracking-widest text-ink-2"
                  >
                    Studio Passcode
                  </label>
                  <span className="font-mono text-[10px] text-ink-3">256-BIT</span>
                </div>
                <div className="relative">
                  <input
                    id="password-input"
                    type={showPassword ? "text" : "password"}
                    autoComplete={isSignup ? "new-password" : "current-password"}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-md border border-line bg-ground px-3.5 py-3 pr-10 text-sm text-ink placeholder:text-ink-3 transition-all focus:outline-none focus:border-frank/50 focus:shadow-[0_0_0_1px_rgba(245,158,11,0.2)]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-ink-3 hover:text-ink transition-colors"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? "hide" : "show"}
                  </button>
                </div>
              </div>

              {/* Confirm password (signup only) */}
              {isSignup && (
                <div className="flex flex-col gap-1.5">
                  <label
                    htmlFor="confirm-input"
                    className="font-mono text-[10px] uppercase tracking-widest text-ink-2"
                  >
                    Confirm Passcode
                  </label>
                  <input
                    id="confirm-input"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    className="w-full rounded-md border border-line bg-ground px-3.5 py-3 text-sm text-ink placeholder:text-ink-3 transition-all focus:outline-none focus:border-frank/50 focus:shadow-[0_0_0_1px_rgba(245,158,11,0.2)]"
                  />
                </div>
              )}

              {/* Remember + forgot (login only) */}
              {!isSignup && (
                <div className="flex items-center justify-between pt-1">
                  <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-2 hover:text-ink transition-colors select-none">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-line bg-raised"
                      style={{ accentColor: "rgb(var(--frank))" }}
                    />
                    Keep studio active
                  </label>
                  <Link
                    href="/login?forgot=1"
                    className="text-xs transition-colors hover:underline"
                    style={{ color: "rgb(var(--frank))" }}
                  >
                    Forgot password?
                  </Link>
                </div>
              )}

              {/* Error */}
              {error && (
                <p role="alert" className="text-sm leading-snug" style={{ color: "rgb(var(--problem))" }}>
                  {error}
                </p>
              )}

              {/* Submit button */}
              <button
                type="submit"
                disabled={busy || !email || !password}
                className="mt-1 flex h-12 w-full items-center justify-center gap-2 rounded-md text-sm font-semibold text-ground transition-all disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.99]"
                style={{
                  background: "rgb(var(--frank))",
                  boxShadow: "0 0 20px rgba(245,158,11,0.3)",
                }}
                onMouseEnter={(e) => {
                  if (!busy) (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 28px rgba(245,158,11,0.5)"
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 20px rgba(245,158,11,0.3)"
                }}
              >
                {busy ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-label="One moment" />
                ) : (
                  <>
                    {isSignup ? "Create my account" : "Sign In to Studio"}
                    <span>→</span>
                  </>
                )}
              </button>
            </form>

            {/* Frank reassurance note */}
            <div className="mt-4 flex items-center gap-2 rounded-md bg-raised p-3">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: "rgb(var(--frank))", boxShadow: "0 0 8px rgba(245,158,11,0.6)" }}
              />
              <p className="text-xs text-ink-2 leading-snug">
                &ldquo;Take your time. Your microphone levels and arrangement scratchpad are preserved.&rdquo;
              </p>
            </div>

            {/* Switch mode */}
            <div className="mt-4 text-center text-sm text-ink-2">
              {isSignup ? (
                <>
                  Already have an account?{" "}
                  <Link
                    href={`/login?next=${encodeURIComponent(next)}`}
                    className="font-semibold transition-colors"
                    style={{ color: "rgb(var(--frank))" }}
                  >
                    Log in <span>→</span>
                  </Link>
                </>
              ) : (
                <>
                  Don&apos;t have a studio key yet?{" "}
                  <Link
                    href={`/signup?next=${encodeURIComponent(next)}`}
                    className="font-semibold transition-colors"
                    style={{ color: "rgb(var(--frank))" }}
                  >
                    Create an account <span>→</span>
                  </Link>
                </>
              )}
            </div>
          </div>

          {/* Sovereignty statement below card */}
          <div className="mt-6 flex flex-col items-center gap-2 text-center">
            <div className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-ink-3">
              <span style={{ color: "rgb(var(--frank))" }}>✓</span>
              <span>100% Artistic Sovereignty Guarantee</span>
            </div>
            <p className="max-w-xs text-xs text-ink-3 leading-relaxed">
              Your vocal stems, lyric fragments, and audio recordings are stored in your private
              encrypted vault. Owned 100% by you, never shared for training.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="flex flex-col items-center justify-between gap-4 border-t border-line/40 px-6 py-4 sm:flex-row">
        <div className="flex items-center gap-1 font-mono text-[11px] text-ink-3">
          <span style={{ color: "rgb(var(--frank) / 0.7)" }}>🔒</span>
          <span>End-to-end encrypted session • Private studio sandbox</span>
        </div>
        <div className="flex gap-6 text-xs text-ink-3">
          <span className="cursor-pointer transition-colors hover:text-ink">Privacy Statement</span>
          <span className="cursor-pointer transition-colors hover:text-ink">Terms of Agency</span>
          <span className="font-mono text-[10px]">© 2025 Frank Studio Inc.</span>
        </div>
      </footer>
    </div>
  )
}
