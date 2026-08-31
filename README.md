# playlist-maker

A Phase 1 implementation of the [Spotify Mood-Arc Playlist Generator spec](docs/spec.md):
two Spotify playlists (**Morning**, **Night**) that follow a fixed mood arc, rebuilt on
demand with a fresh shuffle and no exact repeat of recent rebuilds.

## How it works

Each playlist is made of 5 ordered mood "buckets" (config in
[`config/playlists.json`](config/playlists.json)). Each bucket points at a source Spotify
playlist you curate by hand. On rebuild, the script:

1. Fetches each bucket's source pool.
2. Excludes tracks used in the last N rebuilds of that playlist (no-repeat window).
3. Shuffles what's left and picks the bucket's target song count.
4. Concatenates the buckets in fixed order and overwrites the target playlist.

Night's 5th bucket ("Reading / journaling") is open-ended per the spec — instead of a
fixed song count, the script shuffles and includes the *entire* source pool. Actual
infinite looping/repeat is playback behavior handled by Spotify's own shuffle/repeat
controls when you hit play, not something a static playlist can encode.

Rebuild history (which tracks were used in the last few rebuilds, per playlist) is kept
locally in `data/history.json` — gitignored since it's local runtime state.

## Setup

1. Create a Spotify app at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
   Add `http://127.0.0.1:8888/callback` as a Redirect URI.
2. `cp .env.example .env` and fill in `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` from
   that app.
3. `npm install`
4. `npm run login` — opens a Spotify authorization URL (open it in your browser, approve
   access), then saves tokens to `.spotify-tokens.json` (gitignored).
5. Create your 10 source playlists (5 Morning buckets + 5 Night buckets) and your 2 target
   playlists ("Morning", "Night") on Spotify, seeded per the mood suggestions in
   [`docs/spec.md`](docs/spec.md).
6. Fill in every `sourcePlaylistId` and both `targetPlaylistId` fields in
   [`config/playlists.json`](config/playlists.json) with the real Spotify playlist IDs
   (the ID is the string in a playlist's share link: `open.spotify.com/playlist/<ID>`).

## Usage

```
npm run rebuild:morning
npm run rebuild:night
```

Run these manually whenever you want a fresh version of that playlist (e.g. each morning
or each evening). Automating the trigger (cron, a shortcut, Alexa) is Phase 2 — see
[`docs/spec.md`](docs/spec.md).

## Tuning

- `config/playlists.json` → `noRepeatWindow`: how many past rebuilds to exclude from
  (default 3, per spec).
- `config/playlists.json` → each bucket's `songCount`: songs picked per bucket per
  rebuild (defaults match the spec's time targets).

If a bucket's source pool is too small to satisfy the no-repeat window, the script warns
and falls back to using the full pool for that bucket rather than failing the rebuild.

## Open items from the spec

See the "Open questions" section of [`docs/spec.md`](docs/spec.md) — these are playlist
curation decisions (e.g. the Kohto track for Night bucket 5) that live in your source
playlists, not in this script.
