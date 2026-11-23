/**
 * The one next step for where the song is now (core-path spec 15, requirement 5.1).
 *
 * On 22 Nov the founder went through every room without knowing what to press first: "someone that didn't know
 * what the app is about will find it difficult to use." Every room now shows one line saying what to do next,
 * worked out from what the song already has. It never locks anything: every room stays open.
 */
export type Room = "idea" | "feel" | "beat" | "voice" | "mix" | "export" | "yours"

export interface SongHas {
  feeling: boolean
  music: boolean
  voice: boolean
  blend: boolean
}

export interface NextStep {
  /** What to do, in one short sentence. */
  text: string
  /** The room where it happens. */
  room: Room
  /** True when the step happens in the room the person is already in. */
  here: boolean
}

const ROOM_NAME: Record<Room, string> = {
  idea: "Words",
  feel: "Feeling",
  beat: "Music",
  voice: "Voice",
  mix: "Blend",
  export: "Finish",
  yours: "Yours",
}

export function roomName(room: Room): string {
  return ROOM_NAME[room]
}

function step(room: Room, current: Room, here: string, elsewhere: string): NextStep {
  return { room, here: room === current, text: room === current ? here : elsewhere }
}

export function nextStep(has: SongHas, current: Room): NextStep {
  if (!has.feeling && !has.music) {
    return step("feel", current,
      "Start here: tell Frank how the song should feel, or hum it.",
      "Next: in Feeling, tell Frank how the song should feel, or hum it.")
  }
  if (!has.music) {
    return step("beat", current,
      "Next: build the music from your feeling.",
      "Next: in Music, build the music from your feeling.")
  }
  if (!has.voice) {
    return step("voice", current,
      "Next: press Record and sing over the music. Use headphones if you can.",
      "Next: in Voice, sing over the music.")
  }
  if (!has.blend) {
    return step("mix", current,
      "Next: Frank is putting your voice and the music together. Listen, then say what you'd change.",
      "Next: in Blend, hear your voice and the music together.")
  }
  return step("export", current,
    "Next: when it sounds right, press Finish my song to make a file you can share.",
    "Next: in Finish, make your song ready to share. You can still change anything first.")
}
