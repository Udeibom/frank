// The check run on every room (pasted into the browser through the test tool). Kept so it can be run again.
// Reports: text below the contrast floor, font sizes in use, sideways scroll, clipped controls, amber actions,
// controls sharing an accessible name, and the skip link.
async () => {
  await new Promise((r) => setTimeout(r, 2000))
  const parse = (c) => (c.match(/[\d.]+/g) || []).map(Number)
  const lum = ([r, g, b]) => {
    const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
  }
  const ratio = (a, b) => {
    const x = lum(a), y = lum(b)
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
  }
  const bgOf = (el) => {
    const layers = []
    for (let e = el; e; e = e.parentElement) {
      const c = parse(getComputedStyle(e).backgroundColor)
      const a = c.length > 3 ? c[3] : 1
      if (c.length && a > 0) {
        layers.push([c.slice(0, 3), a])
        if (a >= 1) break
      }
    }
    let base = [20, 17, 14]
    for (let i = layers.length - 1; i >= 0; i--) {
      const [c, a] = layers[i]
      base = base.map((v, k) => c[k] * a + v * (1 - a))
    }
    return base
  }
  const visible = (el) => {
    const cs = getComputedStyle(el)
    const r = el.getBoundingClientRect()
    return cs.visibility !== "hidden" && cs.display !== "none" && r.width > 0 && r.height > 0 && !el.closest(".sr-only")
  }
  const contrast = []
  const sizes = new Set()
  for (const el of document.querySelectorAll("body *")) {
    if (el.closest('[aria-hidden="true"]')) continue
    if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue
    if (!visible(el)) continue
    const cs = getComputedStyle(el)
    sizes.add(parseFloat(cs.fontSize))
    if (el.closest("button:disabled")) continue
    const fg = parse(cs.color)
    const a = fg.length > 3 ? fg[3] : 1
    const bg = bgOf(el)
    const r = ratio(fg.slice(0, 3).map((v, k) => v * a + bg[k] * (1 - a)), bg)
    const size = parseFloat(cs.fontSize)
    const need = size >= 20 ? 3 : 4.5
    if (r < need) contrast.push(`${el.textContent.trim().slice(0, 30)} (${r.toFixed(2)})`)
  }
  const controls = [...document.querySelectorAll("button, a[href], [role=slider], input, textarea, select")].filter(visible)
  const clipped = controls
    .filter((e) => e.tagName === "BUTTON" && e.scrollWidth > e.clientWidth + 1 && !e.querySelector(".truncate"))
    .map((e) => e.textContent.trim().slice(0, 30))
  const offscreen = controls.filter((e) => e.getBoundingClientRect().right > innerWidth + 1).map((e) => (e.getAttribute("aria-label") || e.textContent).trim().slice(0, 30))
  const amber = controls.filter((e) => /\bbg-frank\b/.test(e.className) && !/aria-pressed="true"/.test(e.outerHTML.slice(0, 200)))
  const amberActions = amber.filter((e) => !(e.getAttribute("aria-label") || "").match(/^Pause/)).map((e) => e.textContent.trim().slice(0, 30))
  const names = {}
  for (const e of controls.filter((e) => e.tagName === "BUTTON")) {
    const n = (e.getAttribute("aria-label") || e.textContent).trim()
    if (n) names[n] = (names[n] || 0) + 1
  }
  const dupes = Object.entries(names).filter(([n, c]) => c > 1 && /^(Play|Pause)/.test(n)).map(([n]) => n)
  return {
    room: location.pathname.split("/").pop(),
    width: innerWidth,
    contrastFailures: contrast,
    fontSizes: [...sizes].sort((a, b) => a - b),
    sidewaysScroll: document.documentElement.scrollWidth > innerWidth,
    clipped,
    offscreen,
    amberActions,
    duplicatePlayNames: dupes,
    skipLink: !!document.querySelector('a[href="#stage"]'),
  }
}
