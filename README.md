# soundtrack-engine

A personal soundtrack engine: two Spotify playlists (**Morning**, **Night**) that follow a
fixed emotional arc but are regenerated with fresh, shuffled song selections. See
[`docs/spec_v4.md`](docs/spec_v4.md) for the full project plan (supersedes the earlier
[`docs/spec.md`](docs/spec.md)).

Built incrementally, one phase at a time, per that plan:

- [x] **Phase 1 — Foundation**: project structure, YAML config schema (Pydantic), typing,
      logging, unit tests.
- [x] **Phase 2 — Spotify Layer**: OAuth login, token refresh, playlist read/write.
- [x] **Phase 3 — Generator**: duration-based playlist generation.
- [x] **Phase 4 — History**: SQLite play history, 15-day weighted no-repeat.
- [x] **Phase 5 — Publishing**: on-demand `generate` command, deployed and scheduled
      daily via cron on an Oracle Cloud Always Free VM.

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

## Phase 2 — what's here

- `src/soundtrack_engine/spotify_auth.py` — interactive OAuth login (Authorization Code
  flow via a one-off local callback server) and access-token refresh. The only place that
  reads `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET`.
- `src/soundtrack_engine/token_store.py` — reads/writes `.spotify-tokens.json`
  (gitignored, local only).
- `src/soundtrack_engine/spotify_api_client.py` — `SpotifyApiClient`, the real
  implementation of the `SpotifyClient` protocol: paginated playlist reads, playlist
  overwrite (up to 100 tracks in one call — fine for this project's stage sizes). Also
  has `create_playlist`/`get_current_user_id`, one-time setup helpers outside the
  `SpotifyClient` protocol (the generator/history/publishing phases never create
  playlists, only read/overwrite existing ones).
- `src/soundtrack_engine/bootstrap.py` — fills in any blank playlist ids in config by
  creating real Spotify playlists for them. **Note:** Spotify currently blocks the
  playlist-creation endpoint for this app even with correct scopes (confirmed: modifying
  an existing playlist works, creating a new one doesn't) — so in practice, create
  playlists by hand in Spotify and paste their ids into `config.yaml`; this code is
  ready for if/when creation access is available.
- `src/soundtrack_engine/cli.py` — `soundtrack-engine login`,
  `soundtrack-engine show-playlist <id>` (read-only sanity check for a playlist id), and
  `soundtrack-engine bootstrap-playlists`.
- `tests/test_config.py`, `tests/test_spotify_client.py`, `tests/test_spotify_auth.py`,
  `tests/test_spotify_api_client.py`, `tests/test_token_store.py`, `tests/test_bootstrap.py`
  — unit tests; the Spotify tests mock all HTTP calls, nothing hits the real API.

## Phase 3 — what's here

- `src/soundtrack_engine/generator.py` — `generate_stage_tracks` (weighted-random picks
  from a pool until total duration is within `duration_tolerance_minutes` of a stage's
  `target_minutes`, switching to a best-fit pick as it gets close), `generate_stage`
  (handles a stage's `open_ended` case — the whole pool, shuffled, no duration target),
  and `generate_progression` (runs every stage in order and concatenates the results).
  Takes plain `Track` lists and an optional `weights` list — no Spotify calls, no
  history/database access, fully testable with in-memory data. `weights` defaults to
  uniform; Phase 4's `PlayHistory.weights_for()` is designed to plug straight into it.
  Whichever tracks get picked for a stage, `_diversify_by_artist` then reorders just
  that stage's picks (never across a stage boundary) so same-artist tracks don't land
  back-to-back — best-effort: if one artist is more than half a stage's picks, at least
  one adjacent repeat is unavoidable, but it won't be worse than that.
- `tests/test_generator.py` — unit tests, including the open-ended,
  pool-too-small-for-target fallback, and artist-diversity (both a feasible case with
  zero adjacent repeats and an infeasible one held to the theoretical minimum) cases.

## Phase 4 — what's here

- `src/soundtrack_engine/history.py` — `PlayHistory`, a small SQLite-backed store
  (`data/history.db`, gitignored) of which tracks were generated for which
  progression/stage and when. `weights_for(...)` turns that into the `weights` list
  `generate_stage_tracks` expects: 1.0 for a track never played or last played at/beyond
  `no_repeat_days` ago, ramping linearly down to a small floor (never fully zero — a thin
  pool shouldn't be able to stall generation) the more recently it was played.
- `tests/test_history.py` — unit tests against an in-memory SQLite database.

## Phase 5 — what's here (on-demand half only)

- `src/soundtrack_engine/publish.py` — `rebuild_progression()`: for each stage in a
  progression, fetch its pool, weight it via `PlayHistory`, generate, record the
  generation back to history, then overwrite the output playlist with the full
  concatenated result. This is the wiring the "automatic, on a schedule" half of
  Phase 5 will eventually call — that half (running this on a schedule, on the Oracle
  Cloud VM from the spec's resolved decisions) isn't built yet.
- `soundtrack-engine generate <morning|night>` — runs `rebuild_progression` for real.
- `tests/test_publish.py` — unit tests against a fake `SpotifyClient` and in-memory
  history; no real network calls.

### Deployed: Oracle Cloud VM, cron-scheduled

Running on an Always Free `VM.Standard.E2.1.Micro` instance (Oracle Linux 9), `cron`
firing `generate morning` at 3:00 AM and `generate night` at 3:05 AM Pacific
(`America/Los_Angeles`) daily.

**Python is installed as a portable build, not via `dnf`.** On this instance size
(~500MB–1GB RAM depending on which Micro instance you get), `dnf install` for
`python3.11`/`git` reliably drove the box into severe swap-thrashing and either hung
indefinitely or got OOM-killed — reproduced across two separate instances, with more
swap, with `nice`/`ionice` priority tuning, and with `install_weak_deps=False`, all with
the same result. The fix: download a prebuilt, self-contained CPython 3.11 from
[astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone)
(the `install_only` `x86_64-unknown-linux-gnu` `.tar.gz` build; matches this project's
`requires-python`) to `/opt/python3.11`, and use its bundled `pip` to install this
project's dependencies — pip's resolution for a handful of pure-Python packages is far
lighter than `dnf`'s system-level solver and never triggered the issue. `git` isn't
needed on the server at all — deployment uses [`deploy.sh`](deploy.sh), which pulls a
tarball of `main` straight from GitHub over plain HTTPS (`curl`/`tar`/`cp` only) rather
than `git clone`.

**Auto-deploy before every scheduled run.** `deploy.sh` is chained in front of both cron
entries, so any commit to `main` — from a laptop, from GitHub's web UI, wherever — is
live by the next scheduled generation, with no manual redeploy step:

```
0 3 * * * /opt/playlist-maker/deploy.sh >> /opt/playlist-maker/deploy.log 2>&1 && /opt/playlist-maker/.venv/bin/soundtrack-engine generate morning >> /opt/playlist-maker/generate.log 2>&1
5 3 * * * /opt/playlist-maker/deploy.sh >> /opt/playlist-maker/deploy.log 2>&1 && /opt/playlist-maker/.venv/bin/soundtrack-engine generate night >> /opt/playlist-maker/generate.log 2>&1
```

(swap `/opt/playlist-maker` for the actual deploy path). `deploy.sh` never deletes files
— it only overwrites tracked files with the latest `main` — so `.venv/`, `data/history.db`,
`.env`, and `.spotify-tokens.json` all survive every deploy untouched. It also skips
reinstalling dependencies unless `pyproject.toml` actually changed, so a config-only
commit doesn't cost a `pip` network round-trip on a resource-constrained VM.

One-time setup: `scp deploy.sh` to the server once and `chmod +x` it. Every run after
that pulls its own latest version too, so future changes to `deploy.sh` deploy
themselves. If the repo is ever made private, set a `GITHUB_TOKEN` env var (a read-only,
repo-scoped fine-grained PAT) wherever cron runs — `deploy.sh` picks it up automatically.

## Setup (development)

```
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Copy `.env.example` to `.env` and fill in `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET`
from a [Spotify Developer app](https://developer.spotify.com/dashboard) (Redirect URI:
`http://127.0.0.1:8888/callback`). Then:

```
soundtrack-engine login
soundtrack-engine show-playlist <playlist_id>
```

`login` opens a browser for you to approve access and saves tokens locally; they refresh
automatically after that. `show-playlist` is just a read-only check that a playlist ID is
right and reachable — it's not part of the generator (Phase 3).

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
