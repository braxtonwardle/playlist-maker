#!/usr/bin/env bash
# Syncs this deployment to the latest commit on GitHub's main branch, using only
# curl/tar/cp — no git, no rsync. (Installing python3.11/git via dnf reliably
# OOM'd this VM; keeping this script to core utils avoids reintroducing that.)
#
# Run this in front of the scheduled `generate` commands (see README's Phase 5
# deployment section) so a commit — from GitHub's web UI, a laptop, wherever —
# is live by the next scheduled run, with no manual redeploy step.
#
# One-time setup: copy this file to the server once (e.g. via scp) and
# `chmod +x` it. Every run after that pulls its own latest version too, so
# future improvements to this script deploy themselves.
#
# If the repo is private, set GITHUB_TOKEN in the environment (or in cron's
# crontab -e, or sourced from a file this script `source`s) to a read-only
# fine-grained PAT scoped to this repo.

set -euo pipefail

REPO="braxtonwardle/playlist-maker"
BRANCH="main"
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

TARBALL_URL="https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz"

curl_args=(-fsSL)
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  curl_args+=(-H "Authorization: Bearer ${GITHUB_TOKEN}")
fi

echo "Fetching ${REPO}@${BRANCH}..."
curl "${curl_args[@]}" "$TARBALL_URL" -o "${WORK_DIR}/release.tar.gz"
tar -xzf "${WORK_DIR}/release.tar.gz" -C "$WORK_DIR"

EXTRACTED_DIR=$(find "$WORK_DIR" -mindepth 1 -maxdepth 1 -type d)
if [[ -z "$EXTRACTED_DIR" ]]; then
  echo "Failed to find extracted source directory" >&2
  exit 1
fi

# cp never deletes: .venv/, data/ (history.db), .env, and .spotify-tokens.json
# are all untouched since none of them exist in the tarball (all gitignored).
echo "Copying files into ${DEPLOY_DIR}..."
cp -a "${EXTRACTED_DIR}/." "${DEPLOY_DIR}/"

# Only reinstall dependencies if pyproject.toml actually changed — avoids a
# pip network round-trip on every single scheduled run.
SHA_FILE="${DEPLOY_DIR}/.pyproject.sha256"
NEW_SHA=$(sha256sum "${EXTRACTED_DIR}/pyproject.toml" | awk '{print $1}')
OLD_SHA=""
[[ -f "$SHA_FILE" ]] && OLD_SHA=$(cat "$SHA_FILE")

if [[ "$NEW_SHA" != "$OLD_SHA" ]]; then
  echo "pyproject.toml changed — reinstalling dependencies..."
  "${DEPLOY_DIR}/.venv/bin/pip" install -q -e "${DEPLOY_DIR}"
  echo "$NEW_SHA" > "$SHA_FILE"
else
  echo "Dependencies unchanged, skipping pip install."
fi

echo "Deploy complete."
