/**
 * GET /api/wake — called by the Vercel cron every 10 minutes to keep the
 * Render backend warm. Render free tier spins down after 15 min of inactivity;
 * this prevents that without any external service.
 */
import { NextResponse } from "next/server"

export const runtime = "edge"
export const dynamic = "force-dynamic"

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/health`, {
      // Edge functions have a 10s wall-clock limit; don't hang longer than that.
      signal: AbortSignal.timeout(8000),
    })
    const body = await res.json()
    return NextResponse.json({ ok: res.ok, status: res.status, backend: body })
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: String(err) },
      { status: 503 },
    )
  }
}
