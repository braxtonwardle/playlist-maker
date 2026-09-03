# Personal Soundtrack Engine — Project Plan (v4, handoff version)

This supersedes [`spec.md`](spec.md) (the original v1 spec). Key changes: duration-based
generation instead of song-count, SQLite-backed 30-day (project default; this build uses
**15 days**, see Resolved decisions below) weighted no-repeat instead of a simple
last-3-rebuilds window, YAML config, and a full phased build plan.

## Project Vision

Build a personal soundtrack engine that generates fresh Spotify playlists every day while
preserving carefully designed emotional progressions. The objective is deterministic
emotional journeys with stochastic song selection, not AI-generated playlists from scratch
every day.

## Core Design

- Two progressions to start: **Morning** and **Night**. (Original plan mentioned ~5
  progressions each — start with 1 Morning + 1 Night arc, each built from 5 stages. Treat
  additional progressions as a later expansion, not part of MVP.)
- Each progression consists of multiple emotional stages, in a fixed order.
- Each stage corresponds to a Spotify playlist that acts as a reusable song pool. Target
  40–100+ songs per stage pool over time — the anchor songs are a starting seed, not the
  full pool. Thin pools (under ~15–20 songs) will make the no-repeat logic feel repetitive
  fast.
- The output is a single daily Morning playlist and a single daily Night playlist whose
  contents change but whose emotional arc remains consistent.

## Generation Logic

Generate playlists by target duration, not song count. Keep selecting weighted-random
songs from each stage's pool until the stage duration is close to its target (see Time
Targets below). Near the end of a stage, prefer tracks whose lengths minimize the
remaining gap to target. Targets are soft but firm: stay close (within a couple minutes),
don't treat them loosely.

## Stage Assignment — manual curation, not scoring

A song's stage is simply whichever source playlist you put it in. No audio-feature
analysis or LLM-generated tagging decides stage membership or reorders songs within a
stage — that kind of automatic scoring is explicitly not part of this build (it overlaps
with the excluded Phase 8). Curate each stage's pool by hand. Use known musical
preferences (see Anchor Songs below, and general taste: Bad Bunny, Vulfpeck, Radiohead,
Fleetwood Mac, Rosalía, Teddy Swims, Hozier, Olivia Dean, Chappell Roan, Daft Punk, Hans
Zimmer, Kohto, Childish Gambino, Tame Impala) only as a starting point for suggesting
candidate songs to add to a pool — never for automatically deciding where a song goes.

## Persistence

Store configuration in JSON/YAML and play history in SQLite. Prevent repeats using
weighted randomness favoring songs that have not been heard recently. (This supersedes an
earlier, simpler "avoid last 3 rebuilds" idea — the weighted-by-recency approach is the
intended design.)

## Spotify Integration

Use the Spotify Web API to authenticate, read stage playlists, and replace the contents of
stable output playlists such as "Today's Morning" and "Tonight's Wind Down".

## Time Targets

### Morning (~60 min total, builds toward the back half)

1. Wake / Cinematic — 8 min
2. Groove — 11 min
3. Warm — 12 min
4. Building energy — 14 min
5. Full send / Fun — 15 min

### Night (~60 min for stages 1–4, stage 5 open-ended)

Compressed toward reaching "no lyrics" sooner — stages 1–3 shortened, stage 4 gets more
room. Instrumental descent should begin roughly 30–32 minutes in.

1. Soft landing — 10 min
2. Reflective / emotional — 10 min
3. Deepening / atmospheric — 12 min
4. Instrumental descent — 18–20 min
5. Reading / journaling — open-ended: loop/repeat the stage pool on shuffle rather than a
   fixed duration. This stage needs its own "keep playing until stopped" handling, separate
   from the duration-target logic used in stages 1–4.

## Anchor Songs Per Stage

Starting points to seed each stage's pool by hand directly in Spotify — expand each to
40–100+ songs over time. Songs marked (validated) were confirmed to work well in an
actual generated playlist test run; everything else is a suggestion to curate/cut freely,
not a verified fit. These are reference material only — config never lists songs; see
"Config only holds structure, not songs" below.

### MORNING

1. **Wake / Cinematic** — Time (Hans Zimmer), Day One (Hans Zimmer), Albatross
   (Fleetwood Mac), Cornfield Chase (Hans Zimmer), Mountains (Hans Zimmer), Motion
   Picture Soundtrack (Radiohead)
2. **Groove / Getting moving** — Dean Town (Vulfpeck), Back Pocket (Vulfpeck), 1612
   (Vulfpeck), Khruangbin tracks (e.g. Maria También, Friday Morning), Cómo Se Siente
   (Rosalía)
3. **Warm / Easy** — Dreams (Fleetwood Mac), Reckoner (Radiohead), The Chain (Fleetwood
   Mac), Olivia Dean tracks (Messy, No Man, Dive), Work Song (Hozier)
4. **Building energy** — Freedom (Pharrell), Get Lucky (Daft Punk), Instant Crush (Daft
   Punk), Jungle tracks (Busy Earnin', Happy Man), Redbone (Childish Gambino), Feels Like
   Summer (Childish Gambino)
5. **Full send / Fun** — SAOKO (Rosalía), Titi Me Preguntó (Bad Bunny), Pink Pony Club
   (Chappell Roan), Callaíta (Bad Bunny), Good Luck, Babe! (Chappell Roan), Me Porto
   Bonito (Bad Bunny)

Morning hasn't been test-run yet (unlike Night) — treat this stage set as first-draft
until heard in practice.

### NIGHT

No big-energy stage anywhere — arc winds down the whole way, never builds back up.

1. **Soft landing** (very gentle, intimate, low stimulation) — Songbird (Fleetwood Mac),
   Landslide (Fleetwood Mac), Fade Into You (Mazzy Star), Into Dust (Mazzy Star), Show Me
   How (Lauv), Futile Devices (validated), To Be Alone With You (validated), Butterflies
   feat. AURORA (validated), Naked as We Came (validated)
2. **Reflective / emotional** (still chill, enough movement for a wind-down routine) —
   Holocene (Bon Iver), Re: Stacks (Bon Iver), Should Have Known Better (Sufjan Stevens,
   validated), Messy (Olivia Dean), Heartbeats (The Knife), Stay Alive (validated)
3. **Deepening / atmospheric** (more texture, transitioning toward bed) — Pyramid Song
   (Radiohead, validated), Weird Fishes (Radiohead), Everything In Its Right Place
   (Radiohead), Eventually (Tame Impala), Nude (Radiohead, validated), Shrike (Hozier,
   validated), Glass Eyes (validated)
4. **Instrumental descent** (no lyrics, increasingly ambient/meditative) — S.T.A.Y. (Hans
   Zimmer, validated), No Time for Caution (Hans Zimmer), Says (Nils Frahm), Cornfield
   Chase (Hans Zimmer, validated), Everything Connected (Jordan Rakei)
5. **Reading / journaling** (pure instrumental/ambient, very low cognitive demand) — #19
   (Nils Frahm, validated), 1/1 – Music for Airports (Brian Eno, validated), 1/2 (Brian
   Eno, validated), 2/2 (Brian Eno, validated), A Lovely Place to Be (Ólafur Arnalds,
   validated), Silence – Instrumental (validated), By This River – Phantom (Nils Frahm,
   validated), Hægt kemur ljósið (Sigur Rós, validated), Þú ert jörðin (validated), As a
   Reminder (Nils Frahm, validated), Near Light (Ólafur Arnalds), On the Nature of
   Daylight (Max Richter)

Kohto — still needs specific track title(s) added; not yet resolved.

## Config only holds structure, not songs

`config/config.example.yaml` defines playlist ids, stage order, durations, and generator
settings (`no_repeat_days`, `duration_tolerance_minutes`) — never song lists. Spotify is
the source of truth for what's actually in a stage's pool: add/remove songs directly in
the source playlists on Spotify, using the anchor songs above as a starting point.

## Development Skeleton — MVP scope (build these)

- **Phase 1 – Foundation** — project structure, configuration system, typing, tests,
  logging, and modular architecture.
- **Phase 2 – Spotify Layer** — authentication and playlist read/write operations.
- **Phase 3 – Generator** — duration-based playlist generator using stage pools.
- **Phase 4 – History** — SQLite play history and repeat prevention (weighted randomness).
- **Phase 5 – Publishing** — automatically publish regenerated playlists on a schedule.

A working daily Morning and Night playlist, generated on schedule with no repeats, is the
goal of the MVP. Phases 1–5 are what "done" means for this project.

## Not needed for now (optional, only revisit if MVP feels incomplete after living with it)

- **Phase 6 – Discovery** — configurable percentage of new recommendations, approval
  workflow.
- **Phase 7 – Dashboard** — lightweight Flask/FastAPI UI to edit stages, durations,
  settings.
- **Phase 8 – Intelligence** — metadata scoring, transition optimization,
  weather/schedule modifiers, adaptive learning.

Explicitly out of scope for the initial build. Do not implement unless asked.

## Resolved decisions

- **Triggering mechanism**: automatic scheduling (Phase 5), hosted on Oracle Cloud (likely
  an Always Free tier VM). No Alexa/voice-trigger requirement.
- **Config format**: YAML only, no dashboard/web UI (Phase 7 stays cut).
- **Stage assignment**: manual curation only.
- **Implementation language**: Python (type hints, pydantic config validation, SQLite via
  stdlib).
- **No-repeat window**: 15 days (plan default was 30; shortened per user preference).

## Still open (non-blocking for early phases)

- Kohto track(s) for Night stage 5.
- Pool sizes below their 40–100+ target — will be padded out iteratively by hand.
- Morning pool is unvalidated — only Night has been test-run.
- Songs-per-stage-pool target size — pools need padding before repeat-avoidance is
  meaningful.

## Instructions for Claude Code

Treat Phases 1–5 as a real but scoped software project — clean abstractions, type hints,
unit tests, and documentation, built incrementally one phase at a time. Ask for feedback
after each milestone rather than attempting everything in one pass. Do not build Phases
6–8 unless explicitly requested later.
