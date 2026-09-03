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

- `src/soundtrack_engine/config.py` — Pydantic models (`Config`, `Progression`, `Stage`)
  and `load_config()` for the YAML config.
- `src/soundtrack_engine/logging_setup.py` — shared logging setup.
- `config/config.example.yaml` — the Morning/Night progressions and stages from the spec,
  with each stage's target duration and seed-song suggestions. Not wired to real Spotify
  playlists yet — that starts in Phase 2.
- `tests/test_config.py` — unit tests for config loading and validation.

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
`output_playlist_id`. `seed_songs` are documentation only — the engine reads a stage's
actual source playlist contents, not this list.

`no_repeat_days` controls how far back the (future, Phase 4) history check looks before
re-suggesting a song — currently set to 15.
