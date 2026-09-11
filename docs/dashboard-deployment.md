# Dashboard Deployment (Phase 6)

Deploying the FastAPI dashboard onto the same Oracle Cloud VM that already runs the
cron-scheduled `generate` commands (see README's Phase 5 section). Three things this
needs that the CLI-only deployment didn't: a config file living outside the repo
checkout, a long-running process that survives across deploys, and a way to reach it
from your phone without opening a port on the VM.

## 1. Move the live config outside the repo checkout

`deploy.sh` does `cp -a` from a fresh GitHub tarball over the entire deploy directory
on every run. `config/config.yaml` is a tracked file, so if it stayed inside that
directory, any edit made through the dashboard would get silently overwritten at the
next scheduled generation. Fix: put the live config in a sibling directory that
`deploy.sh` never touches.

```bash
mkdir -p /opt/playlist-maker-config
cp /opt/playlist-maker/config/config.yaml /opt/playlist-maker-config/config.yaml
```

(swap `/opt/playlist-maker` for wherever `deploy.sh`'s `DEPLOY_DIR` actually is). From
now on, both the CLI and the dashboard read/write `SOUNDTRACK_CONFIG_PATH` instead of
the in-repo path — set it once in the `.env` file that already lives next to
`deploy.sh` (gitignored, survives every deploy, same file the Spotify credentials are
already in):

```
SOUNDTRACK_CONFIG_PATH=/opt/playlist-maker-config/config.yaml
```

`config/config.example.yaml` stays in the repo as the versioned template — nothing
about it changes.

## 2. Generate dashboard secrets

```bash
cd /opt/playlist-maker
.venv/bin/soundtrack-engine hash-password
# prompts for a password, prints DASHBOARD_PASSWORD_HASH=...
```

Add to the same `.env`:

```
DASHBOARD_PASSWORD_HASH=<output from the command above>
DASHBOARD_SECRET_KEY=<any long random string — e.g. `openssl rand -hex 32`>
```

Both are read at request time, same as `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET`
already are — no code changes needed to add them.

## 3. Run the dashboard as a systemd user service

A user-level unit avoids needing `sudo` for anything, including restarts from
`deploy.sh`.

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/playlist-dashboard.service <<'EOF'
[Unit]
Description=Playlist Dashboard

[Service]
WorkingDirectory=/opt/playlist-maker
EnvironmentFile=/opt/playlist-maker/.env
ExecStart=/opt/playlist-maker/.venv/bin/uvicorn soundtrack_engine.dashboard.app:app --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now playlist-dashboard.service

# Let the service keep running after you log out of the SSH session, and start on boot:
loginctl enable-linger "$USER"
```

`--host 127.0.0.1`: the dashboard only needs to be reachable from `cloudflared` on the
same machine — never bind it to a public interface directly (see step 4).

`deploy.sh` already restarts this unit automatically after every deploy (via
`systemctl --user restart playlist-dashboard.service`) if it detects the unit is
installed — nothing extra to wire up once this step is done.

## 4. Expose it with a Cloudflare Tunnel

You'll need a domain added to your Cloudflare account (free plan) — the tunnel needs
somewhere to attach a stable hostname. `trycloudflare.com` quick tunnels hand out a
random URL each restart and aren't suitable for something you install once to your
home screen.

```bash
# Install cloudflared (Oracle Linux / RHEL-family):
curl -fsSL -o /tmp/cloudflared.rpm \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-x86_64.rpm
sudo rpm -i /tmp/cloudflared.rpm

# One-time login (opens a URL — approve it for your domain in the browser):
cloudflared tunnel login

# Create a named tunnel and route a hostname to it:
cloudflared tunnel create playlist-dashboard
cloudflared tunnel route dns playlist-dashboard dashboard.yourdomain.com
```

Point the tunnel at the dashboard's local port:

```bash
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml <<'EOF'
tunnel: playlist-dashboard
credentials-file: /home/YOUR_USER/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: dashboard.yourdomain.com
    service: http://127.0.0.1:8000
  - service: http_status:404
EOF
```

Run `cloudflared` as its own user-level systemd service the same way:

```bash
cat > ~/.config/systemd/user/cloudflared.service <<'EOF'
[Unit]
Description=Cloudflare Tunnel

[Service]
ExecStart=/usr/bin/cloudflared tunnel run playlist-dashboard
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now cloudflared.service
```

Nothing needs to be opened in the VM's firewall or Oracle Cloud security list —
`cloudflared` makes only outbound connections to Cloudflare's network, so the VM stays
fully closed to unsolicited inbound traffic even though the dashboard is reachable from
the internet.

Visit `https://dashboard.yourdomain.com` from your iPhone, log in, then use Safari's
Share → **Add to Home Screen** to install it as a standalone app.

## 5. Verify

```bash
# Locally on the VM:
curl -I http://127.0.0.1:8000/login          # 200 from the dashboard itself
systemctl --user status playlist-dashboard   # active (running)
systemctl --user status cloudflared          # active (running)
```

Then from your phone: load `https://dashboard.yourdomain.com/login`, log in, confirm
the page loads with the current live playlist for Ascent/Descent, and try the refresh
(↻) button — it should publish to Spotify and swap in the newly generated track list
(Song / Artist / Bucket / Duration) inline.

## Notes

- `DASHBOARD_SESSION_DAYS` (default 30) controls how long a login session lasts before
  needing the password again.
- `DASHBOARD_COOKIE_SECURE` defaults to `true` (required — the session cookie won't be
  sent otherwise once you're on HTTPS via the tunnel). Only set it to `false` for local
  development over plain `http://localhost`.
- No service worker is included — this is a control panel, not something with a
  meaningful offline mode, so it isn't needed for "Add to Home Screen" to work on iOS.
