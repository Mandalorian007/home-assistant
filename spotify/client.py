"""Spotify Web API client."""

import subprocess
import time
from dataclasses import dataclass

import httpx

from spotify.auth import TokenManager

API_BASE = "https://api.spotify.com/v1"


@dataclass
class PlaybackState:
    """Current playback state."""

    is_playing: bool
    track: str | None
    artist: str | None
    album: str | None
    volume: int | None
    progress_ms: int | None
    duration_ms: int | None
    device_name: str | None


class SpotifyError(Exception):
    """Spotify API error."""

    pass


class PremiumRequiredError(SpotifyError):
    """Raised when Premium is required."""

    pass


class NoActiveDeviceError(SpotifyError):
    """Raised when no active device is found."""

    pass


class SpotifyClient:
    """Spotify Web API client with auto token refresh and device management."""

    def __init__(self) -> None:
        self.token_manager = TokenManager()
        self._http = httpx.Client(timeout=10)

    @property
    def configured(self) -> bool:
        """Check if Spotify is configured."""
        return self.token_manager.configured

    @property
    def authenticated(self) -> bool:
        """Check if user has authenticated."""
        return self.token_manager.load() is not None

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict | None:
        """Make authenticated API request."""
        token = self.token_manager.get_valid_token()
        if not token:
            raise SpotifyError("Not authenticated. Run 'uv run spotify-auth' first.")

        url = f"{API_BASE}{endpoint}"
        response = self._http.request(
            method,
            url,
            params=params,
            json=json,
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code == 204:
            return None

        if response.status_code == 403:
            data = response.json()
            if data.get("error", {}).get("reason") == "PREMIUM_REQUIRED":
                raise PremiumRequiredError(
                    "Spotify Premium is required for playback control."
                )
            raise SpotifyError(data.get("error", {}).get("message", "Forbidden"))

        if response.status_code == 404:
            data = response.json()
            if "No active device" in data.get("error", {}).get("message", ""):
                raise NoActiveDeviceError("No active Spotify device found.")
            raise SpotifyError(data.get("error", {}).get("message", "Not found"))

        response.raise_for_status()
        return response.json() if response.content else None

    def get_devices(self) -> list[dict]:
        """Get available devices."""
        result = self._request("GET", "/me/player/devices")
        return result.get("devices", []) if result else []

    def _find_local_device(self) -> dict | None:
        """Find a device on the local machine."""
        devices = self.get_devices()
        # Look for active device first
        for device in devices:
            if device.get("is_active"):
                return device
        # Fall back to any computer device
        for device in devices:
            if device.get("type") == "Computer":
                return device
        return devices[0] if devices else None

    def _launch_spotify(self) -> bool:
        """Launch Spotify desktop app on macOS."""
        try:
            subprocess.run(
                ["open", "-a", "Spotify"],
                check=True,
                capture_output=True,
                timeout=5,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _ensure_device(self) -> str:
        """Ensure an active device exists, launching Spotify if needed."""
        device = self._find_local_device()
        if device:
            return device["id"]

        # Try to launch Spotify
        if not self._launch_spotify():
            raise NoActiveDeviceError("Could not launch Spotify.")

        # Poll for device
        for _ in range(10):
            time.sleep(1)
            device = self._find_local_device()
            if device:
                return device["id"]

        raise NoActiveDeviceError("Spotify launched but no device appeared.")

    def get_playback_state(self) -> PlaybackState | None:
        """Get current playback state."""
        try:
            result = self._request("GET", "/me/player")
        except SpotifyError:
            return None

        if not result:
            return PlaybackState(
                is_playing=False,
                track=None,
                artist=None,
                album=None,
                volume=None,
                progress_ms=None,
                duration_ms=None,
                device_name=None,
            )

        item = result.get("item", {})
        artists = item.get("artists", [])
        device = result.get("device", {})

        return PlaybackState(
            is_playing=result.get("is_playing", False),
            track=item.get("name"),
            artist=artists[0]["name"] if artists else None,
            album=item.get("album", {}).get("name"),
            volume=device.get("volume_percent"),
            progress_ms=result.get("progress_ms"),
            duration_ms=item.get("duration_ms"),
            device_name=device.get("name"),
        )

    def search(self, query: str, type_: str = "track", limit: int = 5) -> list[dict]:
        """Search for tracks, artists, albums, or playlists."""
        result = self._request(
            "GET",
            "/search",
            params={"q": query, "type": type_, "limit": limit},
        )
        if not result:
            return []

        key = f"{type_}s"  # tracks, artists, albums, playlists
        return result.get(key, {}).get("items", [])

    def play(
        self,
        uri: str | None = None,
        context_uri: str | None = None,
        device_id: str | None = None,
    ) -> None:
        """Start or resume playback."""
        if not device_id:
            device_id = self._ensure_device()

        body: dict = {}
        if context_uri:
            body["context_uri"] = context_uri
        elif uri:
            body["uris"] = [uri]

        self._request(
            "PUT",
            "/me/player/play",
            params={"device_id": device_id} if device_id else None,
            json=body if body else None,
        )

    def pause(self) -> None:
        """Pause playback."""
        self._request("PUT", "/me/player/pause")

    def resume(self) -> None:
        """Resume playback."""
        device_id = self._ensure_device()
        self._request("PUT", "/me/player/play", params={"device_id": device_id})

    def skip(self) -> None:
        """Skip to next track."""
        self._request("POST", "/me/player/next")

    def previous(self) -> None:
        """Go to previous track."""
        self._request("POST", "/me/player/previous")

    def set_volume(self, volume: int) -> None:
        """Set playback volume (0-100)."""
        volume = max(0, min(100, volume))
        self._request("PUT", "/me/player/volume", params={"volume_percent": volume})
