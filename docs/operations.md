# Operations

Day-to-day "how do I..." reference for the deployed system. For first-time setup
(systemd units, Cloudflare Tunnel, installing the dashboard to your phone), see
[`dashboard-deployment.md`](dashboard-deployment.md) instead — this doc assumes that's
already done.

## Where things live

| What | Where |
|---|---|
| Deployed code | `/opt/playlist-maker` (swap for your actual `deploy.sh` `DEPLOY_DIR`) |
| Live config | wherever `SOUNDTRACK_CONFIG_PATH` points — e.g. `/opt/playlist-maker-config/config.yaml`. **Not** `/opt/playlist-maker/config/config.yaml` once this is set; that in-repo path is only the local-dev default. |
| Config backups | `backups/` next to the live config (e.g. `/opt/playlist-maker-config/backups/`) — one timestamped copy per Save |
| Secrets | `/opt/playlist-maker/.env` (gitignored, never in git) |
| Spotify tokens | `/opt/playlist-maker/.spotify-tokens.json` (gitignored) |
| Play history | `/opt/playlist-maker/data/history.db` (gitignored — survives every deploy since `deploy.sh` only overwrites tracked files, and this was never tracked) |
| Deploy/generate logs | `/opt/playlist-maker/deploy.log`, `/opt/playlist-maker/generate.log` (from the cron lines in the README) |

## Deploy / update the code

Normally you don't do anything: `deploy.sh` runs in front of both scheduled cron jobs
(3:00 AM and 3:05 AM Pacific), so a `git push` to `main` — from a laptop, from GitHub's
web UI, wherever — is live by the next scheduled run. It also restarts
`playlist-dashboard.service` automatically after pulling new code, and only reinstalls
Python dependencies if `pyproject.toml` actually changed.

To update immediately instead of waiting for the next cron run:

```bash
ssh your-vm
/opt/playlist-maker/deploy.sh
```

## Change the dashboard password

```bash
cd /opt/playlist-maker
.venv/bin/soundtrack-engine hash-password   # prompts for the new password twice
```

1. Copy the printed `DASHBOARD_PASSWORD_HASH=...` line into `.env`, replacing the old one.
2. Restart the dashboard so it picks up the change (secrets load once at process
   startup, deliberately — see the comment in `dashboard/app.py`):
   ```bash
   systemctl --user restart playlist-dashboard
   ```
3. This alone doesn't log out devices already signed in — their session cookie is
   still valid until `DASHBOARD_SESSION_DAYS` expires. To force every existing session
   to log out immediately (e.g. you think a device/link leaked), also rotate
   `DASHBOARD_SECRET_KEY` in the same `.env` edit (any new random string — that's what
   signs the session cookie, so changing it invalidates all of them at once) before
   restarting.

## Rotate Spotify credentials

1. In the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), open
   the app and regenerate/reveal the client secret.
2. Update `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` in `.env`.
3. Restart the dashboard:
   ```bash
   systemctl --user restart playlist-dashboard
   ```
   The cron-run CLI (`soundtrack-engine generate ...`) doesn't need this step — it's a
   fresh process each time cron fires, so it reads the updated `.env` automatically on
   its next run.
4. Your existing `.spotify-tokens.json` (the saved refresh token) normally keeps
   working straight through a client-secret rotation — no need to re-run
   `soundtrack-engine login` unless Spotify actually starts rejecting requests, in
   which case log in again to get a fresh token pair.

## Restore a config backup

Every dashboard Save copies the previous `config.yaml` into `backups/` (next to the
live config) before writing the new one, named `config.<UTC timestamp>.yaml`.

```bash
ls /opt/playlist-maker-config/backups/
cp /opt/playlist-maker-config/backups/config.20260912T201530123456Z.yaml \
   /opt/playlist-maker-config/config.yaml
```

No restart needed — config is re-read fresh on every dashboard page load and by every
`generate` run, scheduled or manual.

This only covers the dashboard's own Save action. A hand-edit made directly on the
server, or the very first save ever made, has nothing to back up against. If you want
more coverage than that, periodically copy the whole config directory somewhere off
the VM by hand (e.g. `scp`).

## Restart services

```bash
systemctl --user restart playlist-dashboard   # after editing .env, or if it's stuck
systemctl --user restart cloudflared          # if the tunnel drops
systemctl --user status playlist-dashboard
systemctl --user status cloudflared
journalctl --user -u playlist-dashboard -f    # tail live logs
```

## Generate on demand from the command line

Useful if the dashboard or tunnel is down but you still want fresh playlists:

```bash
cd /opt/playlist-maker
.venv/bin/soundtrack-engine generate morning
.venv/bin/soundtrack-engine generate night
```

This is the exact same code path the dashboard's refresh button and the cron jobs use.
