import type { Config } from "tailwindcss"

// Every colour is an RGB-channel variable from globals.css, so `bg-frank/20` and friends work.
const channel = (name: string) => `rgb(var(--${name}) / <alpha-value>)`

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Frank's system (design-and-ui.md + design/stitch/*/DESIGN.md)
        ground: channel("ground"),
        surface: channel("surface"),
        raised: channel("raised"),
        line: channel("line"),
        ink: { DEFAULT: channel("ink"), 2: channel("ink-2"), 3: channel("ink-3") },
        words: channel("words"),
        feel: channel("feel"),
        music: channel("music"),
        voice: channel("voice"),
        frank: channel("frank"),
        "frank-shade": channel("frank-shade"),
        "frank-glow": channel("frank-glow"),
        "frank-text": channel("frank-text"),
        "frank-container": channel("frank-container"),
        "surface-lowest": channel("surface-lowest"),
        "surface-low": channel("surface-low"),
        "surface-container": channel("surface-container"),
        "surface-high": channel("surface-high"),
        "surface-highest": channel("surface-highest"),
        "on-surface": channel("on-surface"),
        "on-surface-variant": channel("on-surface-variant"),
        "on-primary": channel("on-primary"),
        tertiary: channel("tertiary"),
        ok: channel("ok"),
        caution: channel("caution"),
        problem: channel("problem"),
        // shadcn names (mapped to the tokens above)
        background: channel("background"),
        foreground: channel("foreground"),
        card: { DEFAULT: channel("card"), foreground: channel("card-foreground") },
        popover: { DEFAULT: channel("popover"), foreground: channel("popover-foreground") },
        primary: { DEFAULT: channel("primary"), foreground: channel("primary-foreground") },
        secondary: { DEFAULT: channel("secondary"), foreground: channel("secondary-foreground") },
        muted: { DEFAULT: channel("muted"), foreground: channel("muted-foreground") },
        accent: { DEFAULT: channel("accent"), foreground: channel("accent-foreground") },
        destructive: { DEFAULT: channel("destructive"), foreground: channel("destructive-foreground") },
        border: channel("border"),
        input: channel("input"),
        ring: channel("ring"),
      },
      borderRadius: {
        // Stitch roundedness level 2: 8px default
        lg: "var(--radius)",          // 8px — studio panels, trays
        md: "calc(var(--radius) - 2px)", // 6px — inputs, standard buttons  (kept compat)
        sm: "0.25rem",                // 4px — smallest elements
        xl: "1rem",                   // 16px — sliding panels (top corners)
        "2xl": "1.5rem",              // 24px — large cards
        full: "9999px",               // pills and badges
      },
      fontFamily: {
        // Loaded in app/layout.tsx with next/font/local and exposed as CSS variables.
        // Stitch: Plus Jakarta Sans (tool/studio text), Newsreader (user/artistic), Space Mono (timestamps/code)
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        written: ["var(--font-written)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "Courier New", "monospace"],
      },
      // Type scale: Stitch spec + prior 5-step scale kept for backward compat
      fontSize: {
        // Stitch label scales
        "label-sm": ["0.6875rem", { lineHeight: "0.875rem", letterSpacing: "0.06em" }], // 11/14
        "label-md": ["0.75rem",   { lineHeight: "1rem",     letterSpacing: "0.04em" }], // 12/16
        // Utility names (backward compat — existing code uses these)
        xs:   ["0.75rem",   { lineHeight: "1rem" }],       // 12/16
        sm:   ["0.8125rem", { lineHeight: "1.125rem" }],   // 13/18 body-sm
        base: ["0.875rem",  { lineHeight: "1.25rem" }],    // 14/20 body-md (frank-voice)
        lg:   ["1rem",      { lineHeight: "1.5rem" }],     // 16/24 body-lg
        xl:   ["1.25rem",   { lineHeight: "1.875rem" }],   // 20/30 user-lyric-display
        "2xl": ["1.5rem",   { lineHeight: "2rem" }],       // 24/32 headline-md
        "3xl": ["2rem",     { lineHeight: "2.5rem" }],     // 32/40 headline-lg
        "4xl": ["2.5rem",   { lineHeight: "3rem" }],       // 40/48 headline-xl
      },
      boxShadow: {
        // Elevation system (design/stitch/*/DESIGN.md)
        l2: "0 8px 24px rgba(0, 0, 0, 0.45)",          // L2: cards, active channels
        l3: "0 20px 48px rgba(0, 0, 0, 0.65)",          // L3: modals, overlays, popovers
        "frank-luminescence": "0 0 16px rgba(245, 158, 11, 0.25)", // Active Frank glow
        "play-bloom": "0 0 20px 4px rgba(245, 158, 11, 0.35)",     // Play button active
        "play-bloom-lg": "0 0 28px 8px rgba(245, 158, 11, 0.4)",   // Stage play button active
      },
      keyframes: {
        "pulse-amber": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
        filamentPulse: {
          "0%, 100%": { opacity: "0.4" },
          "50%": { opacity: "1" },
        },
        filamentSweep: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        "pulse-amber": "pulse-amber 2s ease-in-out infinite",
        "slide-in-right": "slide-in-right 0.2s ease-out",
        "filament-pulse": "filamentPulse 2s ease-in-out infinite",
        "filament-sweep": "filamentSweep 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}

export default config
