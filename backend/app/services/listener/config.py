"""
Listener thresholds, in one place. Each says where the number came from, so it can be argued with.
Units are internal (loudness units, milliseconds, 0..1 shares); none of them is ever shown to the person.
"""

# A chorus should be heard as a lift. Mixers usually want a chorus 2-4 loudness units above the verse;
# under 1.5 the ear reads the two as the same strength. (producer-craft.md: chorus lift; engine target is ~3 dB.)
CHORUS_LIFT_MIN = 1.5
CHORUS_LIFT_STRONG_PROBLEM = 0.5          # under this the two are effectively identical

# Two same-named sections are "a copy" above this similarity. Calibrated on engine renders: a verse that
# returns with different parts and moments measures roughly 0.80-0.93; an exact repeat measures above 0.98.
COPY_SIMILARITY = 0.97

# Voice against beat. A lead vocal normally sits within a few units of the music or above it.
# Below -3 the words start to be covered (common mixing guidance: vocal at or slightly above the bed).
VOCAL_BURIED_GAP = -3.0
# In the 200-4000 Hz range (where words live) the beat should not be much louder than the voice.
VOICE_RANGE_CROWDED_GAP = -4.0

# Timing. Singers sit within about 30 ms of the beat and it still feels tight; past 45 ms a listener
# starts to feel the voice is behind or ahead. Needs a clear measurement to be believed.
TIMING_OFFSET_MS = 45.0
TIMING_MIN_CONFIDENCE = 0.35

# Singing against the song's notes: share of voiced time within 35 cents of a note in the song's scale.
# Untrained singers usually land 60-80%; under 55 is notable.
IN_TUNE_WITHIN_CENTS = 35.0
IN_TUNE_MIN_SHARE = 0.55
MIN_VOICED_SECONDS = 3.0

# Melody: share of strong-beat notes that belong to the chord underneath. The engine guarantees ~1.0.
MELODY_FIT_MIN = 0.6

# Safety
CLIPPING_SHARE = 0.001                    # more than 0.1% of samples at full scale is audible as harshness
NOISE_FLOOR_DB = -50.0                    # a quiet room is about -60; above -50 the hiss is audible between phrases
MIX_TOO_QUIET_LUFS = -24.0                # streaming targets are about -14; under -24 is clearly low
MIX_TOO_LOUD_LUFS = -8.0

# The whole song is flat if no section differs from its neighbour by more than this.
FLAT_CHANGE = 0.12

# Findings are only believed when at least this much of the song could be measured.
MIN_SECTION_SECONDS = 1.0
