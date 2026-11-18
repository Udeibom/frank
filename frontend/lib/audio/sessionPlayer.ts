/**
 * SessionPlayer — plays the beat and the sing-along guide together, sample-accurately, from any point in the song
 * (sing-it spec 06, requirement 1). Playback only: the browser never processes audio (audio-architecture rule 1).
 * Timing: `play()` returns when (in performance.now() milliseconds) the beat actually starts, so a recording that
 * began earlier can say how long it ran before the beat came in.
 */

export interface PlayOptions {
  /** Where in the song to start, seconds. */
  from: number
  /** Loop between `from` and this point (practice). */
  loopTo?: number | null
  /** Beats of clicks before the music starts (count-in when starting at the very top). */
  clicks?: number
  secondsPerBeat?: number
  guideLevel?: number
}

export class SessionPlayer {
  private ctx: AudioContext | null = null
  private buffers = new Map<string, AudioBuffer>()
  private sources: AudioScheduledSourceNode[] = []
  private guideGain: GainNode | null = null

  private context(): AudioContext {
    if (!this.ctx || this.ctx.state === "closed") this.ctx = new AudioContext()
    return this.ctx
  }

  async load(url: string): Promise<AudioBuffer> {
    const hit = this.buffers.get(url)
    if (hit) return hit
    const data = await (await fetch(url)).arrayBuffer()
    const buf = await this.context().decodeAudioData(data)
    this.buffers.set(url, buf)
    return buf
  }

  /** Map an AudioContext time to performance.now() milliseconds. */
  private perfTime(ctxTime: number): number {
    const ctx = this.context()
    const ts = ctx.getOutputTimestamp?.()
    if (ts && ts.contextTime !== undefined && ts.performanceTime !== undefined && ts.performanceTime > 0) {
      return ts.performanceTime + (ctxTime - ts.contextTime) * 1000
    }
    return performance.now() + (ctxTime - ctx.currentTime) * 1000
  }

  private click(at: number, accent: boolean) {
    const ctx = this.context()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.frequency.value = accent ? 1500 : 1000
    gain.gain.setValueAtTime(0.0001, at)
    gain.gain.exponentialRampToValueAtTime(0.5, at + 0.002)
    gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.06)
    osc.connect(gain).connect(ctx.destination)
    osc.start(at)
    osc.stop(at + 0.08)
    this.sources.push(osc)
  }

  /** Clicks only (the timing check). Returns the performance.now() time of each click. */
  async clicks(count: number, every: number, startIn = 0.5): Promise<number[]> {
    const ctx = this.context()
    await ctx.resume()
    const t0 = ctx.currentTime + startIn
    const times: number[] = []
    for (let k = 0; k < count; k++) {
      this.click(t0 + k * every, k === 0)
      times.push(this.perfTime(t0 + k * every))
    }
    return times
  }

  /**
   * Start the beat (and the guide, when given) at `from`. Returns the performance.now() time at which the beat
   * starts sounding, after any count-in clicks.
   */
  async play(beatUrl: string, guideUrl: string | null, opts: PlayOptions): Promise<number> {
    this.stop()
    const ctx = this.context()
    await ctx.resume()
    const [beat, guide] = await Promise.all([this.load(beatUrl), guideUrl ? this.load(guideUrl) : Promise.resolve(null)])
    const spb = opts.secondsPerBeat ?? 0.6
    const clicks = opts.clicks ?? 0
    const at = ctx.currentTime + 0.25
    for (let k = 0; k < clicks; k++) this.click(at + k * spb, k === 0)
    const musicAt = at + clicks * spb
    const start = (buf: AudioBuffer, dest: AudioNode) => {
      const src = ctx.createBufferSource()
      src.buffer = buf
      if (opts.loopTo && opts.loopTo > opts.from) {
        src.loop = true
        src.loopStart = opts.from
        src.loopEnd = Math.min(opts.loopTo, buf.duration)
      }
      src.connect(dest)
      src.start(musicAt, Math.min(opts.from, Math.max(0, buf.duration - 0.05)))
      this.sources.push(src)
    }
    start(beat, ctx.destination)
    if (guide) {
      this.guideGain = ctx.createGain()
      this.guideGain.gain.value = opts.guideLevel ?? 0.5
      this.guideGain.connect(ctx.destination)
      start(guide, this.guideGain)
    }
    return this.perfTime(musicAt)
  }

  setGuideLevel(level: number) {
    if (this.guideGain) this.guideGain.gain.value = level
  }

  stop() {
    for (const s of this.sources) {
      try {
        s.stop()
      } catch {
        // already stopped
      }
    }
    this.sources = []
    this.guideGain = null
  }

  close() {
    this.stop()
    this.ctx?.close()
    this.ctx = null
  }
}
