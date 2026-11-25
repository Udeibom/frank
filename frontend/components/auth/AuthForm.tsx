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
import { cn } from "@/lib/utils"

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

const inputClass =
  "w-full rounded-lg border border-line bg-raised px-3.5 py-3 text-sm text-ink placeholder:text-ink-3 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-frank/40 focus-visible:border-frank/50"

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter()
  const params = useSearchParams()
  const next = safeNext(params.get("next"))

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
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
    <main className="flex min-h-screen items-center justify-center px-4">
      {/* Ambient amber bloom behind the card */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 60%, rgb(var(--frank) / 0.07) 0%, transparent 70%)",
        }}
      />

      <div className="w-full max-w-sm">
        {/* Frank wordmark */}
        <div className="mb-8 text-center">
          <span
            className="font-written italic text-5xl leading-none select-none"
            style={{ color: "rgb(var(--frank))" }}
            aria-label="Frank"
          >
            f
          </span>
          <h1 className="mt-4 font-written italic text-2xl text-ink">
            {isSignup ? "Start your studio" : "Welcome back"}
          </h1>
          <p className="mt-2 text-sm text-ink-2">
            {isSignup
              ? "Make an account so your songs stay yours."
              : "Pick up where you left off."}
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-7 shadow-l2"
          noValidate
        >
          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-2">
            Email
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="you@example.com"
            />
          </label>

          <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-2">
            Password
            <input
              type="password"
              autoComplete={isSignup ? "new-password" : "current-password"}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
          </label>

          {isSignup && (
            <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-2">
              Type it once more
              <input
                type="password"
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className={inputClass}
              />
            </label>
          )}

          {error && (
            <p role="alert" className="text-sm text-problem leading-snug">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !email || !password}
            className={cn(
              "mt-1 flex items-center justify-center gap-2 rounded-full py-3 text-sm font-semibold transition-all duration-150",
              "bg-frank text-ground hover:bg-frank-shade",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-label="One moment" />
            ) : isSignup ? (
              "Create my account"
            ) : (
              "Log in"
            )}
          </button>
        </form>

        <p className="mt-5 text-center text-sm text-ink-3">
          {isSignup ? (
            <>
              Already have an account?{" "}
              <Link href={`/login?next=${encodeURIComponent(next)}`} className="text-ink underline underline-offset-4 hover:text-frank transition-colors">
                Log in
              </Link>
            </>
          ) : (
            <>
              New here?{" "}
              <Link href={`/signup?next=${encodeURIComponent(next)}`} className="text-ink underline underline-offset-4 hover:text-frank transition-colors">
                Make an account
              </Link>
            </>
          )}
        </p>
      </div>
    </main>
  )
}
