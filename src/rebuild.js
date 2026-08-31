import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpotifyClient } from "./spotifyClient.js";
import { loadHistory, saveHistory, getExcludedUris, recordRebuild } from "./history.js";
import { shuffle } from "./shuffle.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CONFIG_PATH = path.join(__dirname, "..", "config", "playlists.json");

function loadConfig() {
  return JSON.parse(readFileSync(CONFIG_PATH, "utf8"));
}

/**
 * Picks tracks for one bucket: exclude recently-used URIs, shuffle what's left,
 * and take songCount (or everything, for an open-ended bucket like Night's
 * "Reading / journaling"). Falls back to the full pool if exclusion leaves too
 * few candidates, so a small hand-curated source playlist doesn't stall a rebuild.
 */
function pickBucketTracks(bucket, poolUris, excludedUris) {
  let candidates = poolUris.filter((uri) => !excludedUris.has(uri));

  const needed = bucket.openEnded ? candidates.length || poolUris.length : bucket.songCount;
  if (candidates.length < needed) {
    console.warn(
      `  "${bucket.name}": only ${candidates.length} non-repeated tracks available, falling back to full pool.`
    );
    candidates = poolUris;
  }

  shuffle(candidates);
  return bucket.openEnded ? candidates : candidates.slice(0, bucket.songCount);
}

async function rebuildPlaylist(playlistKey) {
  const config = loadConfig();
  const playlistConfig = config[playlistKey];
  if (!playlistConfig) {
    throw new Error(`Unknown playlist "${playlistKey}" — expected "morning" or "night".`);
  }
  if (!playlistConfig.targetPlaylistId) {
    throw new Error(
      `config/playlists.json: ${playlistKey}.targetPlaylistId is not set yet.`
    );
  }

  const client = new SpotifyClient();
  const history = loadHistory();
  const excludedUris = getExcludedUris(history, playlistKey, config.noRepeatWindow);

  console.log(`Rebuilding "${playlistKey}" (excluding ${excludedUris.size} recently-used tracks)...`);

  const finalUris = [];
  for (const bucket of playlistConfig.buckets) {
    if (!bucket.sourcePlaylistId) {
      throw new Error(
        `config/playlists.json: bucket "${bucket.name}" in "${playlistKey}" has no sourcePlaylistId set.`
      );
    }

    const poolUris = await client.fetchAllPlaylistTrackUris(bucket.sourcePlaylistId);
    if (poolUris.length === 0) {
      throw new Error(`Bucket "${bucket.name}" source playlist is empty — add some songs first.`);
    }

    const picks = pickBucketTracks(bucket, poolUris, excludedUris);
    console.log(`  "${bucket.name}": picked ${picks.length} of ${poolUris.length} pool tracks.`);
    finalUris.push(...picks);
  }

  await client.replacePlaylistTracks(playlistConfig.targetPlaylistId, finalUris);
  recordRebuild(history, playlistKey, finalUris, config.noRepeatWindow);
  saveHistory(history);

  console.log(`Done — wrote ${finalUris.length} tracks to the "${playlistKey}" playlist.`);
}

const playlistKey = process.argv[2];
if (playlistKey !== "morning" && playlistKey !== "night") {
  console.error("Usage: node src/rebuild.js <morning|night>");
  process.exit(1);
}

rebuildPlaylist(playlistKey).catch((err) => {
  console.error(err.message);
  process.exit(1);
});
