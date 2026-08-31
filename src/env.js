import { config } from "dotenv";

config();

function required(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing ${name} in .env. Copy .env.example to .env and fill it in.`
    );
  }
  return value;
}

export function getSpotifyEnv() {
  return {
    clientId: required("SPOTIFY_CLIENT_ID"),
    clientSecret: required("SPOTIFY_CLIENT_SECRET"),
    redirectUri: process.env.SPOTIFY_REDIRECT_URI || "http://127.0.0.1:8888/callback",
  };
}
