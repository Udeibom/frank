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
    <div className="stitch-auth flex min-h-screen flex-col text-ink">
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

      <main className="relative flex flex-1 flex-col items-center justify-center px-4 py-16">
        <div
          aria-hidden="true"
          className="pointer-events-none fixed inset-0 -z-10"
          style={{
            background: isSignup
              ? "radial-gradient(ellipse 60% 50% at 50% 62%, rgba(84,221,252,0.07) 0%, transparent 70%), radial-gradient(ellipse 50% 40% at 50% 40%, rgba(245,158,11,0.06) 0%, transparent 70%)"
              : "radial-gradient(ellipse 60% 50% at 50% 60%, rgba(245,158,11,0.07) 0%, transparent 70%)",
          }}
        />

        <div className={isSignup ? "w-full max-w-[490px]" : "w-full max-w-[460px]"}>
          <div className="stitch-auth-card p-8">
            <span className="stitch-auth-rail" aria-hidden="true" />
            <span className="absolute left-2.5 top-2.5 h-1.5 w-1.5 rounded-full bg-surface-highest opacity-60" aria-hidden="true" />
            <span className="absolute right-2.5 top-2.5 h-1.5 w-1.5 rounded-full bg-surface-highest opacity-60" aria-hidden="true" />
            <span className="absolute bottom-2.5 left-2.5 h-1.5 w-1.5 rounded-full bg-surface-highest opacity-60" aria-hidden="true" />
            <span className="absolute bottom-2.5 right-2.5 h-1.5 w-1.5 rounded-full bg-surface-highest opacity-60" aria-hidden="true" />

            <div className="mb-6 flex flex-col items-center gap-3 text-center">
              <div
                className="flex h-16 w-16 items-center justify-center rounded-2xl border border-frank/30 bg-frank/10"
                style={{ boxShadow: "inset 0 0 22px rgba(245,158,11,0.08), 0 0 28px rgba(245,158,11,0.12)" }}
              >
                <span className="font-written text-[40px] italic leading-none text-frank select-none">f</span>
              </div>
              <p className="stitch-kicker text-ink-3">Master Console &bull; Rack 01</p>
            </div>

            <h1 className="stitch-title text-center text-ink">
              {isSignup ? (
                "Open your studio"
              ) : (
                <>
                  Welcome back to{" "}
                  <em className="font-written italic text-frank">Frank</em>
                </>
              )}
            </h1>
            <p className="mx-auto mt-2 mb-7 max-w-md text-sm leading-relaxed text-ink-2">
              {isSignup
                ? "No complex audio gear or music words. Just you, your ideas, and your personal co-writer."
                : "Everything you've made is right where you left it."}
            </p>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
              {/* Email field */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="email-input"
                    className="font-mono text-[10px] uppercase tracking-widest text-ink-2"
                  >
                    Email address
                  </label>
                  <span className="font-mono text-[10px] text-ink-3">PRIVATE</span>
                </div>
                <input
                  id="email-input"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full rounded-lg border border-line bg-surface-lowest px-4 py-3.5 text-sm text-on-surface placeholder:text-ink-3 transition-all focus:border-frank/60 focus:shadow-[0_0_0_1px_rgba(245,158,11,0.25)] focus:outline-none"
                />
              </div>

              {/* Password field */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="password-input"
                    className="font-mono text-[10px] uppercase tracking-widest text-ink-2"
                  >
                    Password
                  </label>
                  <span className="font-mono text-[10px] text-ink-3">PRIVATE</span>
                </div>
                <div className="relative">
                  <input
                    id="password-input"
                    type={showPassword ? "text" : "password"}
                    autoComplete={isSignup ? "new-password" : "current-password"}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full rounded-lg border border-line bg-surface-lowest px-4 py-3.5 pr-10 text-sm text-on-surface placeholder:text-ink-3 transition-all focus:border-frank/60 focus:shadow-[0_0_0_1px_rgba(245,158,11,0.25)] focus:outline-none"
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

              {isSignup && password.length > 0 && (
                <div className="-mt-1 flex items-center gap-3">
                  <div className="flex flex-1 gap-1" aria-hidden="true">
                    {[1, 2, 3].map((step) => (
                      <span
                        key={step}
                        className="h-1 flex-1 rounded-full"
                        style={{
                          background:
                            password.length >= step * 4
                              ? step === 3 && password.length >= 12
                                ? "rgb(var(--ok))"
                                : "rgb(var(--frank))"
                              : "rgb(var(--surface-highest))",
                        }}
                      />
                    ))}
                  </div>
                  <span className="font-mono text-[10px] uppercase tracking-widest text-ink-3">
                    Longer is stronger
                  </span>
                </div>
              )}

              {isSignup && (
                <div className="flex flex-col gap-1.5">
                  <label
                    htmlFor="confirm-input"
                    className="font-mono text-[10px] uppercase tracking-widest text-ink-2"
                  >
                    Confirm password
                  </label>
                  <input
                    id="confirm-input"
                    type="password"
                    autoComplete="new-password"
                    required
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    className="w-full rounded-lg border border-line bg-surface-lowest px-4 py-3.5 text-sm text-on-surface placeholder:text-ink-3 transition-all focus:border-frank/60 focus:shadow-[0_0_0_1px_rgba(245,158,11,0.25)] focus:outline-none"
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

              {error && (
                <p role="alert" className="rounded-lg border border-problem/40 bg-problem/10 px-4 py-3 text-sm leading-snug text-problem">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={busy || !email || !password}
                className="stitch-primary mt-2 flex h-12 w-full items-center justify-center gap-2 text-sm disabled:cursor-not-allowed disabled:bg-surface-high disabled:text-ink-3 disabled:shadow-none"
              >
                {busy ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-label="One moment" />
                ) : (
                  <>
                    {isSignup ? "Create studio account" : "Sign in to studio"}
                    <span aria-hidden="true">→</span>
                  </>
                )}
              </button>
            </form>

            <div className="stitch-bay mt-5 flex items-center gap-3 px-4 py-3">
              <span className="h-2 w-2 shrink-0 rounded-full bg-frank shadow-[0_0_8px_rgb(var(--frank)/0.6)]" />
              <p className="text-xs leading-snug text-ink-2">
                &ldquo;Take your time. Your work stays here while you write, record, and blend.&rdquo;
              </p>
            </div>

            <div className="mt-5 border-t border-line/60 pt-4 text-center text-sm text-ink-2">
              {isSignup ? (
                <>
                  Already have a studio?{" "}
                  <Link
                    href={`/login?next=${encodeURIComponent(next)}`}
                    className="font-semibold text-frank transition-colors hover:text-frank-glow"
                  >
                    Sign in <span aria-hidden="true">→</span>
                  </Link>
                </>
              ) : (
                <>
                  Need a studio of your own?{" "}
                  <Link
                    href={`/signup?next=${encodeURIComponent(next)}`}
                    className="font-semibold text-frank transition-colors hover:text-frank-glow"
                  >
                    Create one <span aria-hidden="true">→</span>
                  </Link>
                </>
              )}
            </div>
          </div>

          <div className="mt-6 flex flex-col items-center gap-2 text-center">
            <div className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-ink-3">
              <span className="text-frank">✓</span>
              <span>Your work stays yours</span>
            </div>
            <p className="max-w-sm text-xs leading-relaxed text-ink-3">
              Your songs, words, and recordings stay private. We never use them to train other models.
            </p>
          </div>
        </div>
      </main>

      <footer className="flex flex-col items-center justify-between gap-4 border-t border-line/40 px-6 py-4 sm:flex-row">
        <div className="flex items-center gap-2 font-mono text-[11px] text-ink-3">
          <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-frank/70" />
          <span>Private studio session</span>
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
