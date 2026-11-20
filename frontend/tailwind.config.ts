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
        // Frank's system (design-and-ui.md)
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
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        // The faces are loaded in app/layout.tsx with next/font and exposed as these variables.
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        written: ["var(--font-written)", "Georgia", "serif"],
      },
      // The type scale: five sizes only (design-and-ui.md). Nothing under 12px.
      fontSize: {
        xs: ["0.75rem", { lineHeight: "1rem" }],      // 12/16
        sm: ["0.8125rem", { lineHeight: "1.125rem" }], // 13/18
        base: ["0.9375rem", { lineHeight: "1.375rem" }], // 15/22
        xl: ["1.25rem", { lineHeight: "1.625rem" }],   // 20/26
        "2xl": ["1.5rem", { lineHeight: "1.75rem" }],  // 24/28
      },
      keyframes: {
        // Kept only for the not-yet-redesigned Voice room's recording button.
        "pulse-amber": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
      },
      animation: {
        "pulse-amber": "pulse-amber 2s ease-in-out infinite",
        "slide-in-right": "slide-in-right 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}

export default config
