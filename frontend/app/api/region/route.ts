/**
 * The visitor's country, as Vercel sees it (frankenstein spec 14, requirement 9.1). Frank's backend uses it only
 * to keep Google's free listening and looking helper away from the EEA, Switzerland and the UK, as Google's
 * terms require. Nothing is stored.
 */
import { NextRequest, NextResponse } from "next/server"

export const runtime = "edge"
export const dynamic = "force-dynamic"

export function GET(req: NextRequest) {
  const country = req.headers.get("x-vercel-ip-country") ?? ""
  return NextResponse.json({ country: /^[A-Z]{2}$/.test(country) ? country : null }, { headers: { "Cache-Control": "no-store" } })
}
