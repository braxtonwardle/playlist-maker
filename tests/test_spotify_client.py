from soundtrack_engine.models import Track
from soundtrack_engine.spotify_client import SpotifyClient


class FakeSpotifyClient:
    """A minimal stand-in used to prove the protocol's shape without hitting Spotify."""

    def fetch_playlist_tracks(self, playlist_id: str) -> list[Track]:
        return [Track(uri=f"spotify:track:{playlist_id}", duration_ms=180_000)]

    def replace_playlist_tracks(self, playlist_id: str, track_uris: list[str]) -> None:
        return None


class IncompleteClient:
    def fetch_playlist_tracks(self, playlist_id: str) -> list[Track]:
        return []


def test_conforming_class_satisfies_spotify_client_protocol() -> None:
    assert isinstance(FakeSpotifyClient(), SpotifyClient)


def test_incomplete_class_does_not_satisfy_protocol() -> None:
    assert not isinstance(IncompleteClient(), SpotifyClient)


def test_track_holds_uri_and_duration() -> None:
    track = Track(uri="spotify:track:abc123", duration_ms=210_000)
    assert track.uri == "spotify:track:abc123"
    assert track.duration_ms == 210_000
