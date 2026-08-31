import { getSpotifyEnv } from "./env.js";
import { loadTokens, saveTokens } from "./tokenStore.js";

const API_BASE = "https://api.spotify.com/v1";
const REFRESH_MARGIN_MS = 60 * 1000;

export class SpotifyClient {
  async #getAccessToken() {
    const tokens = loadTokens();
    if (!tokens) {
      throw new Error("Not logged in yet. Run `npm run login` first.");
    }

    if (Date.now() < tokens.expires_at - REFRESH_MARGIN_MS) {
      return tokens.access_token;
    }

    const { clientId, clientSecret } = getSpotifyEnv();
    const response = await fetch("https://accounts.spotify.com/api/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Authorization: "Basic " + Buffer.from(`${clientId}:${clientSecret}`).toString("base64"),
      },
      body: new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: tokens.refresh_token,
      }),
    });

    if (!response.ok) {
      throw new Error(`Token refresh failed: ${response.status} ${await response.text()}`);
    }

    const data = await response.json();
    const updated = {
      access_token: data.access_token,
      // Spotify doesn't always return a new refresh_token; keep the old one if absent.
      refresh_token: data.refresh_token || tokens.refresh_token,
      expires_at: Date.now() + data.expires_in * 1000,
    };
    saveTokens(updated);
    return updated.access_token;
  }

  async #request(pathOrUrl, options = {}) {
    const accessToken = await this.#getAccessToken();
    const url = pathOrUrl.startsWith("http") ? pathOrUrl : `${API_BASE}${pathOrUrl}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`Spotify API error ${response.status} on ${url}: ${await response.text()}`);
    }

    if (response.status === 204) return null;
    return response.json();
  }

  /** Returns the ordered list of track URIs in a playlist, skipping local files and removed tracks. */
  async fetchAllPlaylistTrackUris(playlistId) {
    const uris = [];
    let url = `${API_BASE}/playlists/${playlistId}/tracks?fields=items(track(uri,is_local)),next&limit=100`;

    while (url) {
      const page = await this.#request(url);
      for (const item of page.items) {
        if (item.track && !item.track.is_local && item.track.uri) {
          uris.push(item.track.uri);
        }
      }
      url = page.next;
    }

    return uris;
  }

  /** Overwrites a playlist's contents with the given ordered list of track URIs (max 100). */
  async replacePlaylistTracks(playlistId, uris) {
    if (uris.length > 100) {
      throw new Error(
        `replacePlaylistTracks got ${uris.length} URIs; this simple implementation only supports up to 100 in one request.`
      );
    }
    await this.#request(`/playlists/${playlistId}/tracks`, {
      method: "PUT",
      body: JSON.stringify({ uris }),
    });
  }
}
