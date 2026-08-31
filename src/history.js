import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, "..", "data");
const HISTORY_PATH = path.join(DATA_DIR, "history.json");

export function loadHistory() {
  if (!existsSync(HISTORY_PATH)) return {};
  return JSON.parse(readFileSync(HISTORY_PATH, "utf8"));
}

export function saveHistory(history) {
  mkdirSync(DATA_DIR, { recursive: true });
  writeFileSync(HISTORY_PATH, JSON.stringify(history, null, 2));
}

/** Flattened set of track URIs used in the last `windowSize` rebuilds of `playlistKey`. */
export function getExcludedUris(history, playlistKey, windowSize) {
  const rebuilds = history[playlistKey] || [];
  const recent = rebuilds.slice(-windowSize);
  return new Set(recent.flat());
}

/** Appends this rebuild's track list to history, trimmed to the no-repeat window. */
export function recordRebuild(history, playlistKey, uris, windowSize) {
  const rebuilds = history[playlistKey] || [];
  rebuilds.push(uris);
  history[playlistKey] = rebuilds.slice(-windowSize);
}
