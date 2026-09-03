# soundtrack-engine

A personal soundtrack engine: two Spotify playlists (**Morning**, **Night**) that follow a
fixed emotional arc but are regenerated with fresh, shuffled song selections. See
[`docs/spec_v4.md`](docs/spec_v4.md) for the full project plan (supersedes the earlier
[`docs/spec.md`](docs/spec.md)).

Built incrementally, one phase at a time, per that plan:

- [x] **Phase 1 — Foundation**: project structure, YAML config schema (Pydantic), typing,
      logging, unit tests.
- [ ] **Phase 2 — Spotify Layer**: authentication and playlist read/write.
- [ ] **Phase 3 — Generator**: duration-based playlist generation.
- [ ] **Phase 4 — History**: SQLite play history, 15-day weighted no-repeat.
- [ ] **Phase 5 — Publishing**: scheduled regeneration.

## Phase 1 — what's here

- `src/soundtrack_engine/config.py` — Pydantic models (`Config`, `GeneratorSettings`,
  `Progression`, `Stage`) and `load_config()` for the YAML config. Config only holds
  playlist ids, stage order, durations, and generator settings — never song lists.
- `src/soundtrack_engine/models.py` — `Track`, the one domain type Spotify data gets
  converted into before anything else in the engine sees it.
- `src/soundtrack_engine/spotify_client.py` — `SpotifyClient`, the single protocol every
  later phase talks to Spotify through. Implemented in Phase 2; keeps Spotify SDK/HTTP
  calls from leaking into the generator, history, or publishing code.
- `src/soundtrack_engine/logging_setup.py` — shared logging setup.
- `config/config.example.yaml` — the Morning/Night progressions and stages from the spec,
  each stage with a stable `id` (separate from its display `name`) and target duration.
  Not wired to real Spotify playlists yet — that starts in Phase 2. Song suggestions per
  stage live in `docs/spec_v4.md`, not in config.
- `tests/test_config.py`, `tests/test_spotify_client.py` — unit tests for config
  validation and the Spotify client contract.

## Setup (development)

```
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

## Config

Copy `config/config.example.yaml` to `config/config.yaml` before Phase 2 needs real
playlist IDs. Each stage needs a `source_playlist_id` (the ID from a playlist's share
link: `open.spotify.com/playlist/<ID>`); each progression needs an
`output_playlist_id`. Spotify is the source of truth for what songs are actually in a
stage's pool — config never lists songs; see `docs/spec_v4.md` for starter song
suggestions to add directly in Spotify.

Each stage also has an `id` (stable, snake_case) separate from its `name` (display
label) — the id won't change even if you rename a stage later.

The `generator` section is the home for playlist-generation settings:
`no_repeat_days` (currently 15) controls how far back the future Phase 4 history check
looks before re-suggesting a song; `duration_tolerance_minutes` (currently 2) controls
how close a stage's generated length must land to its `target_minutes`.
