import { createServer } from "node:http";
import { randomBytes } from "node:crypto";
import { getSpotifyEnv } from "./env.js";
import { saveTokens } from "./tokenStore.js";

const SCOPES = [
  "playlist-read-private",
  "playlist-read-collaborative",
  "playlist-modify-public",
  "playlist-modify-private",
].join(" ");

async function main() {
  const { clientId, clientSecret, redirectUri } = getSpotifyEnv();
  const state = randomBytes(16).toString("hex");
  const redirect = new URL(redirectUri);

  const authorizeUrl = new URL("https://accounts.spotify.com/authorize");
  authorizeUrl.searchParams.set("client_id", clientId);
  authorizeUrl.searchParams.set("response_type", "code");
  authorizeUrl.searchParams.set("redirect_uri", redirectUri);
  authorizeUrl.searchParams.set("scope", SCOPES);
  authorizeUrl.searchParams.set("state", state);

  console.log("Open this URL in a browser and approve access:\n");
  console.log(authorizeUrl.toString());
  console.log(`\nWaiting for the redirect back to ${redirectUri} ...`);

  const code = await new Promise((resolve, reject) => {
    const server = createServer((req, res) => {
      const url = new URL(req.url, `http://${req.headers.host}`);
      if (url.pathname !== redirect.pathname) {
        res.writeHead(404).end();
        return;
      }

      const error = url.searchParams.get("error");
      const returnedState = url.searchParams.get("state");
      const returnedCode = url.searchParams.get("code");

      if (error) {
        res.writeHead(400, { "Content-Type": "text/plain" }).end(`Auth failed: ${error}`);
        server.close();
        reject(new Error(`Spotify authorization failed: ${error}`));
        return;
      }
      if (returnedState !== state) {
        res.writeHead(400, { "Content-Type": "text/plain" }).end("State mismatch.");
        server.close();
        reject(new Error("OAuth state mismatch — possible CSRF, aborting."));
        return;
      }

      res.writeHead(200, { "Content-Type": "text/plain" }).end(
        "Login successful — you can close this tab and return to the terminal."
      );
      server.close();
      resolve(returnedCode);
    });

    server.listen(Number(redirect.port) || 80, redirect.hostname);
  });

  const tokenResponse = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization: "Basic " + Buffer.from(`${clientId}:${clientSecret}`).toString("base64"),
    },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: redirectUri,
    }),
  });

  if (!tokenResponse.ok) {
    throw new Error(`Token exchange failed: ${tokenResponse.status} ${await tokenResponse.text()}`);
  }

  const tokenData = await tokenResponse.json();
  saveTokens({
    access_token: tokenData.access_token,
    refresh_token: tokenData.refresh_token,
    expires_at: Date.now() + tokenData.expires_in * 1000,
  });

  console.log("\nLogged in. Tokens saved to .spotify-tokens.json.");
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
