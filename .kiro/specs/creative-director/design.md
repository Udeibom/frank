# Creative Director - Design (spec 10)

## Identity brief writer
`services/team/identity.py`: one model call (Creative Director role card) over: the intent facet, the feeling
facet, the lyrics, the person's own messages (last 40), decisions (chosen/rejected), vocal facts (raw or tuned
preference). Output JSON `{own_words: [..], own_images: [..], voice: str, keep: [..], avoid: [..]}` written as a
new `identity_brief` facet version. Runs after: lyrics saved, a direction chosen, a take kept, at most once per
10 minutes per project (job).

## Named artists
Detection in the router (spec 07): the router JSON gets `named_reference: str|null`. When set, the Creative
Director card answers with ONE question about what they love, and on the reply the feeling words go into the
feeling facet (`loved_qualities`); the name is stored in the `references` facet with `use: "feeling_only"` and
is never passed to the composer or to any prompt as a target. No web tool is given to any role.

## Drift check
Code check before executing directions or `VocalTune{mode: full}` and lyric replacements: compare the change
against `keep` items (lyric lines/images by text match; voice character flags). On hit, the Producer's reply
gets one line from the Creative Director. Recorded as a decision.
