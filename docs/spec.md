# Spotify Mood-Arc Playlist Generator — Spec

## Goal

Two Spotify playlists (Morning, Night) that follow a fixed mood arc every day, but pull
different songs (and different order within each mood) each time they're rebuilt — no
exact repeat of yesterday's playlist.

## Core logic

- Each playlist has 5 ordered "buckets" (moods). Bucket order is always fixed.
- Each bucket has a source pool: a Spotify playlist you maintain by hand, adding/removing
  songs over time.
- On each rebuild: shuffle within each bucket, pick N songs per bucket, avoid songs played
  in the last few days (no-repeat window), concatenate buckets in order, write result into
  the Morning or Night playlist.
- Morning and Night have **separate** bucket pools — no shared source playlists.

## Suggested rebuild parameters (defaults — tune later)

- No-repeat window: exclude songs used in the last 3 rebuilds of that playlist.
- Songs per bucket: start with 3–4 per bucket (≈15–20 songs total per playlist).
- Time targets are soft targets: aim for song *count* per bucket that lands near the
  target minutes (assuming ~3.5–4 min/song average), not exact duration matching. Close
  enough is fine.

## Time targets

### Morning (~60 min total, builds toward the back half)

1. Wake / Cinematic — 8 min (~2 songs)
2. Groove — 11 min (~3 songs)
3. Warm — 12 min (~3 songs)
4. Building energy — 14 min (~4 songs)
5. Full send / Fun — 15 min (~4 songs)

### Night (~60 min for buckets 1–4, bucket 5 open-ended)

Compressed toward getting to "no lyrics" sooner — buckets 1–3 shortened, bucket 4 gets
more room. Reaches instrumental descent around the 32-min mark.

1. Soft landing — 10 min (~3 songs)
2. Reflective / emotional — 10 min (~3 songs)
3. Deepening / atmospheric — 12 min (~3 songs)
4. Instrumental descent — 18–20 min (~5 songs)
5. Reading / journaling — open-ended: loop/repeat the source pool on shuffle rather than a
   fixed song count. Selection logic here differs from buckets 1–4 — needs its own "keep
   playing until stopped" handling rather than a target minute count.

## Phase 1 (build first)

- Spotify Developer app + OAuth to get API access.
- Script that reads the 5 source playlists per mood, applies shuffle + no-repeat logic,
  writes to the target playlist (Morning or Night).
- Triggered manually (e.g. a script you run, or a button/shortcut).

## Phase 2 (later)

- Voice trigger via Alexa. Likely path: Alexa Routine + webhook (e.g. IFTTT) calling the
  script, then a second step to tell Alexa to play the playlist on Spotify. Not yet
  verified — treat as unconfirmed until tested. Alternative: custom Alexa Skill talking
  directly to a hosted function (e.g. AWS Lambda) — more setup, more "native" feel.
- Needs the script hosted somewhere reachable 24/7 (small server or serverless function),
  since Alexa can't run a local script directly.

## MORNING — buckets (source playlist pools)

1. **Wake / Cinematic** — Time, Day One, Albatross
2. **Groove / Getting moving** — Dean Town, Back Pocket, Khruangbin
3. **Warm / Easy** — Dreams, Reckoner, Olivia Dean
4. **Building energy** — Freedom, Get Lucky, Jungle
5. **Full send / Fun** — SAOKO, Titi Me Preguntó, Pink Pony Club

## NIGHT — buckets (source playlist pools)

No big-energy bucket — arc winds all the way down instead of building up.

1. **Soft landing** (very gentle, intimate, low stimulation) — Songbird, Landslide, Fade
   Into You, Into Dust, Show Me How
2. **Reflective / emotional** (still chill, enough movement for winding-down routine) —
   Holocene, Re: Stacks, Should Have Known Better, Messy, Heartbeats
3. **Deepening / atmospheric** (more momentum/texture, transitioning toward bed) —
   Pyramid Song, Weird Fishes, Everything In Its Right Place, Eventually
4. **Instrumental descent** (no lyrics, increasingly ambient/meditative) — S.T.A.Y., No
   Time for Caution, Says, Everything Connected
5. **Reading / journaling** (pure instrumental/ambient, very low cognitive demand) — Nils
   Frahm — Hammers; Ólafur Arnalds — Near Light; Max Richter — On the Nature of Daylight;
   Brian Eno — 1/1 (Music for Airports); Kohto — [add specific track(s); no confident
   title suggested]

Note: "Says" was listed in both bucket 3 and bucket 4 in the original draft — moved to
bucket 4 only (instrumental descent) since it fits that mood better. Flag if you wanted it
in bucket 3 instead.

## Open questions / things to nail down before or during build

- Songs-per-bucket count for each playlist (can differ between Morning/Night).
- Exact no-repeat window length (how many days back to exclude).
- Kohto track(s) for Night bucket 5 — needs your input, not populated above.
- Whether "Titi Me Preguntó" appearing in Morning only now, or if you want it
  removed/duplicated elsewhere.
- Where the rebuild script will run/live for Phase 1 (local machine vs. some hosted
  environment) — affects how Phase 2 (Alexa) attaches later.
