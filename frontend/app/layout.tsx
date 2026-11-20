import type { Metadata } from "next"
import localFont from "next/font/local"
import "./globals.css"

// Frank's two voices (design-and-ui.md): the tool speaks in Inter; the user's own words are set in Newsreader.
// The files live in app/fonts (both SIL Open Font License, latin subset, variable weight) so the right faces
// render on every build, with or without a network connection. A font that silently falls back is how the
// old interface ended up in the system font.
const sans = localFont({
  src: [{ path: "./fonts/Inter-latin.woff2", weight: "400 600", style: "normal" }],
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

export const metadata: Metadata = {
  title: "Frank",
  description: "Use Frank. Turn your ideas into songs.",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`dark ${sans.variable} ${written.variable}`}>
      <body className="min-h-screen bg-background text-foreground antialiased font-sans">
        {children}
      </body>
    </html>
  )
}
