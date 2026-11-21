---
title: frank-ears
emoji: 👂
colorFrom: gray
colorTo: yellow
sdk: gradio
sdk_version: 5.50.0
python_version: "3.11"
app_file: app.py
pinned: false
license: agpl-3.0
short_description: Models Frank listens with (API for Frank)
suggested_hardware: zero-a10g
---

# frank-ears

Part of [Frank](https://github.com/Udeibom/frank), a music studio for people with no music training. This Space is
an API, not an app: Frank's backend sends it short audio and words and gets back what the models hear.

| Endpoint | Model | Licence |
|---|---|---|
| `/embed_audio`, `/embed_text` | LAION CLAP `larger_clap_music_and_speech` | Apache-2.0 |
| `/labels` | MTG Discogs-EffNet + MTG-Jamendo mood head (Essentia models) | CC BY-NC-SA 4.0 |
| `/aesthetics` | Meta Audiobox Aesthetics | CC BY 4.0 |
| `/structure` | All-In-One music structure analyzer | MIT |
| `/chords` | madmom CNN + CRF chord recognition | BSD code, CC BY-NC-SA models |
| `/separate` | BS-RoFormer via audio-separator | MIT |
| `/pitch` | PESTO | LGPL-3.0 |
| `/emotions` | GoEmotions (`SamLowe/roberta-base-go_emotions`) | MIT |
| `/match_master` | Matchering 2 | GPL-3.0 |
| `/denoise` | DeepFilterNet 3 | MIT / Apache-2.0 |

Non-commercial use only (several model licences require it). Audio sent here is processed and not kept.
