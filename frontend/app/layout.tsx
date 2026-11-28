import type { Metadata, Viewport } from "next"
import localFont from "next/font/local"
import "./globals.css"

/**
 * Frank's three typographic voices (design-and-ui.md + design/stitch/[room]/DESIGN.md):
 *   • Plus Jakarta Sans  — the studio: tool text, labels, Frank's voice (500), UI metadata
 *   • Newsreader         — the artist: user words, song lyrics, creative intent (italic optional)
 *   • Space Mono         — the clock: timestamps, version markers, duration counters
 *
 * All files are local woff2 (latin subset) so the right faces render on every build
 * without a network round-trip, consistent with the free-tier deployment constraint.
 */
const sans = localFont({
  src: [{ path: "./fonts/PlusJakartaSans-latin.woff2", weight: "400 600", style: "normal" }],
  variable: "--font-sans",
  display: "swap",
  fallback: ["system-ui", "sans-serif"],
})

const written = localFont({
  src: [
    { path: "./fonts/Newsreader-latin.woff2", weight: "400 500", style: "normal" },
    { path: "./fonts/Newsreader-italic-latin.woff2", weight: "400 500", style: "italic" },
  ],
  variable: "--font-written",
  display: "swap",
  fallback: ["Georgia", "serif"],
})

const mono = localFont({
  src: [{ path: "./fonts/SpaceMono-latin.woff2", weight: "400", style: "normal" }],
  variable: "--font-mono",
  display: "swap",
  fallback: ["Courier New", "monospace"],
})

export const metadata: Metadata = {
  title: "Frank",
  description: "Use Frank. Turn your ideas into songs.",
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#121316",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`dark ${sans.variable} ${written.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-background text-foreground antialiased font-sans">
        {children}
      </body>
    </html>
  )
}
