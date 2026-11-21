---
title: frank-hands
emoji: 🖐️
colorFrom: gray
colorTo: yellow
sdk: gradio
sdk_version: 5.50.0
python_version: "3.10"
app_file: app.py
pinned: false
license: agpl-3.0
short_description: Models Frank makes music with (API for Frank)
suggested_hardware: zero-a10g
---

# frank-hands

Part of [Frank](https://github.com/Udeibom/frank). An API, not an app: Frank's backend asks it for notes and sounds,
and Frank's own engine keeps control of the song.

| Endpoint | Model | Licence |
|---|---|---|
| `/accompany` | Anticipatory Music Transformer `stanford-crfm/music-medium-800k` | Apache-2.0 |
| `/timbre` | DDSP timbre transfer (Magenta pretrained solo instruments) | Apache-2.0 |
| `/speak` | Kokoro-82M | Apache-2.0 |
| `/ambience` | Stable Audio 3 Small / Open | Stability AI Community Licence |
| `/sing` | DiffSinger with the Tiger voicebank (downloaded from its release, not redistributed) | CC BY-NC-ND 4.0 + Commons Clause |

Non-commercial use only. Audio sent here is processed and not kept.
