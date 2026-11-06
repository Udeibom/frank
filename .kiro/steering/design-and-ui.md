# Frank — Design and UI Principles

## The Studio Metaphor

Frank looks and feels like a studio, not a software tool. Every design decision should reinforce the feeling that the user is in a creative space, not filling out a form or configuring a system.

The UI is warm, focused, and alive. Audio is always one click from playing. The user can always hear what they have.

## Visual Language

- **Dark theme by default** — studios are dark. Dark background with warm accent colors.
- **Primary color**: deep warm background (#0D0D0D or similar)
- **Accent**: amber/warm gold — energy, warmth, creativity
- **Text**: off-white, never pure white
- **No harsh edges** — rounded corners, soft shadows
- **Waveforms**: visible whenever audio exists. The user should always be able to see their sound.

## Navigation

The studio has six layers. The user navigates between them freely. The navigation is always visible — a clean sidebar or top bar showing all six layers with status indicators:

- Empty circle: not started
- Partial fill: in progress
- Filled: has content
- No locks. No "you must complete this before that."

## The Conversation Panel

- Always present, on the right side or collapsible
- Shows the current conversation for the active layer
- Clean, minimal — no chatbot avatar, no branding in the conversation
- The user's messages on the right, Frank's on the left
- Frank's messages that triggered an action show a subtle indicator: "► Beat adjusted"
- The input is at the bottom, always focused

## Audio Controls

Every piece of audio in Frank has a consistent play/pause control:
- Single large play button — no ambiguity
- Progress bar that is clickable (scrub to any point)
- Duration shown
- Waveform shown when possible

For comparing takes or versions:
- Side by side cards, each with its own play control
- A "compare" mode that plays them alternating at the same position

## Feedback and Loading States

Loading states must never be blank spinners. Every async operation shows:
- What is happening: "Building your beat..."
- Approximate time if known: "This usually takes about 30 seconds"
- Something for the user to do in the meantime if possible

Error states must be in plain language:
- Never: "Error 500: Internal Server Error"
- Always: "Something went wrong building the beat — want to try again?"

## No Music Jargon in the UI

Labels, buttons, section titles, tooltips — none of them use technical music terms without a plain-language alternative. Examples:

- Not "Apply reverb" → "Add space"
- Not "Adjust tempo" → "Change the speed"
- Not "Pitch correction" → "Tune my vocals"
- Not "Export stems" → "Download separate parts"

## Responsiveness

Desktop-first for this MVP (web-based studio with recording is primarily a desktop use case), but the layout must not break on tablet. Mobile is explicitly not a target for this version.

Minimum supported width: 1024px

## Component Library

Use shadcn/ui components as the base. Do not build from scratch what shadcn provides. Customize via Tailwind CSS. Keep the component layer thin — Frank's UI is not complex in its components, it's complex in its audio interactions.

## Accessibility

- All interactive elements must be keyboard accessible
- All audio controls must have ARIA labels
- Color is never the only indicator of state
- Focus management must be correct — especially in the recording flow where the user might have a microphone in hand
