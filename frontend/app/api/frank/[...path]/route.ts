/**
 * /api/frank/[...path] — server-side proxy to the Render backend.
 *
 * Render's Cloudflare WAF drops any request whose combined headers + body
 * exceed 512 bytes. Supabase JWTs are ~930 bytes, so every authenticated
 * browser request was silently dropped. Routing through this Vercel API route
 * keeps the JWT server-side: the browser sends the token to Vercel over HTTPS,
 * Vercel forwards it to Render from a trusted server IP that the WAF allows.
 */
import { NextRequest, NextResponse } from "next/server"

const BACKEND = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export const dynamic = "force-dynamic"

async function proxy(req: NextRequest, path: string): Promise<NextResponse> {
  const url = `${BACKEND}/${path}${req.nextUrl.search}`

  // Forward all headers the client sent, except the Host header and
  // Accept-Encoding — we don't decompress/re-compress, so ask for plain text.
  const headers = new Headers()
  req.headers.forEach((value, key) => {
    if (key.toLowerCase() !== "host" && key.toLowerCase() !== "accept-encoding") {
      headers.set(key, value)
    }
  })

  let body: BodyInit | undefined
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await req.arrayBuffer()
  }

  try {
    const upstream = await fetch(url, {
      method: req.method,
      headers,
      body,
      // Edge functions have a 10s wall-clock limit; use a service worker
      // pattern for long jobs (they poll separately). Auth + simple DB ops
      // complete in < 5s when the backend is warm.
      signal: AbortSignal.timeout(55_000),
    })

    const responseHeaders = new Headers()
    upstream.headers.forEach((value, key) => {
      // Strip hop-by-hop and encoding headers — we buffer the full body,
      // so the browser must not try to decompress or use the wrong length.
      const skip = ["connection", "transfer-encoding", "keep-alive",
                    "content-encoding", "content-length"]
      if (!skip.includes(key.toLowerCase())) {
        responseHeaders.set(key, value)
      }
    })

    // Buffer the full body so Next.js computes the correct Content-Length.
    const responseBody = await upstream.arrayBuffer()
    return new NextResponse(responseBody, {
      status: upstream.status,
      headers: responseHeaders,
    })
  } catch (err) {
    const isTimeout = err instanceof Error && err.name === "TimeoutError"
    return NextResponse.json(
      { detail: isTimeout ? "Frank is taking a moment — try again." : "Frank couldn't reach the studio just now." },
      { status: 503 },
    )
  }
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path.join("/"))
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path.join("/"))
}

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path.join("/"))
}

export async function DELETE(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path.join("/"))
}

export async function PUT(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path.join("/"))
}

export async function OPTIONS(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params
  return proxy(req, path.join("/"))
}
