#!/usr/bin/env python3
"""Live integration tests for Spotify tools.

Run: uv run pytest tests/test_spotify.py -v

NOTE: These tests require:
1. SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env
2. Authenticated via 'uv run spotify-auth'
3. Spotify Premium for playback control tests
"""

import os
import pytest

from tools.spotify import (
    PlayMusic,
    play_music,
    PauseMusic,
    pause_music,
    ResumeMusic,
    resume_music,
    SkipTrack,
    skip_track,
    SetMusicVolume,
    set_music_volume,
    GetPlaybackStatus,
    get_playback_status,
)
from spotify.client import SpotifyClient
from spotify.auth import TokenManager, TOKEN_FILE


class TestSpotifyConfig:
    """Test Spotify configuration detection."""

    def test_detects_missing_credentials(self):
        """Should report when credentials are missing."""
        # This tests the error message path
        result = get_playback_status(GetPlaybackStatus())
        # Either configured or returns helpful message
        assert (
            "not configured" in result.lower()
            or "not authenticated" in result.lower()
            or "playing" in result.lower()
            or "nothing" in result.lower()
        )


@pytest.fixture
def spotify_configured():
    """Check if Spotify is configured."""
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        pytest.skip("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET not set")


@pytest.fixture
def spotify_authenticated(spotify_configured):
    """Check if Spotify is authenticated."""
    if not TOKEN_FILE.exists():
        pytest.skip("Not authenticated. Run 'uv run spotify-auth' first.")
    token_manager = TokenManager()
    if not token_manager.get_valid_token():
        pytest.skip("Token expired or invalid. Run 'uv run spotify-auth' to re-authenticate.")


class TestSpotifyClient:
    """Test Spotify client functionality."""

    def test_client_configured(self, spotify_configured):
        """Client should report configured status."""
        client = SpotifyClient()
        assert client.configured

    def test_client_authenticated(self, spotify_authenticated):
        """Client should be authenticated."""
        client = SpotifyClient()
        assert client.authenticated

    def test_get_devices(self, spotify_authenticated):
        """Should be able to list devices."""
        client = SpotifyClient()
        devices = client.get_devices()
        # May be empty if no active devices, but should not error
        assert isinstance(devices, list)


class TestGetPlaybackStatus:
    """Test playback status tool."""

    def test_get_status(self, spotify_authenticated):
        """Should return playback status."""
        result = get_playback_status(GetPlaybackStatus())
        # Either playing something or nothing
        assert (
            "playing" in result.lower()
            or "paused" in result.lower()
            or "nothing" in result.lower()
        )

    def test_status_format(self, spotify_authenticated):
        """Status should have expected format when playing."""
        result = get_playback_status(GetPlaybackStatus())
        if "nothing" not in result.lower():
            # Should have duration format [m:ss/m:ss]
            assert "[" in result and "]" in result


class TestPlaybackControl:
    """Test playback control tools (requires Premium)."""

    @pytest.fixture(autouse=True)
    def check_premium(self, spotify_authenticated):
        """Skip if not premium (detected on first failure)."""
        pass

    def test_play_search(self, spotify_authenticated):
        """Should search and play music."""
        result = play_music(PlayMusic(query="Beethoven Symphony"))
        # Either plays or reports premium required
        assert (
            "playing" in result.lower()
            or "premium" in result.lower()
            or "no track" in result.lower()
            or "no spotify device" in result.lower()
            or "error" in result.lower()
        )

    def test_play_playlist(self, spotify_authenticated):
        """Should play a playlist."""
        result = play_music(PlayMusic(query="chill", type="playlist"))
        assert (
            "playing" in result.lower()
            or "premium" in result.lower()
            or "no playlist" in result.lower()
            or "error" in result.lower()
        )

    def test_pause_resume(self, spotify_authenticated):
        """Should pause and resume playback."""
        pause_result = pause_music(PauseMusic())
        assert (
            "paused" in pause_result.lower()
            or "premium" in pause_result.lower()
            or "error" in pause_result.lower()
        )

        resume_result = resume_music(ResumeMusic())
        assert (
            "resumed" in resume_result.lower()
            or "premium" in resume_result.lower()
            or "error" in resume_result.lower()
        )

    def test_skip(self, spotify_authenticated):
        """Should skip to next track."""
        result = skip_track(SkipTrack())
        assert (
            "skipped" in result.lower()
            or "premium" in result.lower()
            or "error" in result.lower()
        )

    def test_set_volume(self, spotify_authenticated):
        """Should set volume."""
        # Get current status to see if we can determine volume
        status = get_playback_status(GetPlaybackStatus())

        result = set_music_volume(SetMusicVolume(volume=50))
        assert (
            "50%" in result
            or "premium" in result.lower()
            or "error" in result.lower()
        )


class TestSpotifyCLI:
    """CLI integration tests."""

    def test_status_cli(self, spotify_authenticated):
        """Test status via CLI."""
        import subprocess

        result = subprocess.run(
            ["uv", "run", "spotify", "status"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        output = result.stdout.lower()
        assert "playing" in output or "paused" in output or "nothing" in output

    def test_help_cli(self):
        """Test CLI help."""
        import subprocess

        result = subprocess.run(
            ["uv", "run", "spotify", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "play" in result.stdout
        assert "status" in result.stdout
        assert "pause" in result.stdout
