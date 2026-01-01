#!/usr/bin/env python3
"""Spotify playback control tools.

CLI: uv run spotify play "chill jazz"
     uv run spotify status
     uv run spotify pause
     uv run spotify resume
     uv run spotify skip
     uv run spotify volume 50
Tool: Registered as PlayMusic, GetPlaybackStatus, etc. for OpenAI function calling
"""

from pydantic import BaseModel, Field

from spotify.client import (
    SpotifyClient,
    SpotifyError,
    PremiumRequiredError,
    NoActiveDeviceError,
)


# ─── Models ────────────────────────────────────────────────────────────────


class PlayMusic(BaseModel):
    """Play music on Spotify by searching for a track, artist, album, or playlist."""

    query: str = Field(description="Search query (e.g., 'chill jazz', 'Beatles')")
    type: str = Field(
        default="track",
        description="Type to search: 'track', 'artist', 'album', or 'playlist'",
    )


class PauseMusic(BaseModel):
    """Pause Spotify playback."""

    pass


class ResumeMusic(BaseModel):
    """Resume Spotify playback."""

    pass


class SkipTrack(BaseModel):
    """Skip to the next track on Spotify."""

    pass


class SetMusicVolume(BaseModel):
    """Set Spotify playback volume. Use this for music/media volume, not device volume."""

    volume: int = Field(
        description="Volume level from 0 to 100",
        ge=0,
        le=100,
    )


class GetPlaybackStatus(BaseModel):
    """Get current Spotify playback status including track, artist, and volume."""

    pass


# ─── Handlers ──────────────────────────────────────────────────────────────


def _get_client() -> SpotifyClient:
    """Get configured Spotify client."""
    return SpotifyClient()


def _format_duration(ms: int | None) -> str:
    """Format milliseconds as m:ss."""
    if ms is None:
        return "0:00"
    seconds = ms // 1000
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def play_music(params: PlayMusic) -> str:
    """Play music on Spotify."""
    client = _get_client()

    if not client.configured:
        return "Spotify not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env"

    if not client.authenticated:
        return "Spotify not authenticated. Run 'uv run spotify-auth' to connect your account."

    try:
        # Search for content
        results = client.search(params.query, params.type)
        if not results:
            return f"No {params.type}s found for '{params.query}'"

        item = results[0]
        uri = item.get("uri")
        name = item.get("name", "Unknown")

        # Get artist for tracks
        artist = ""
        if params.type == "track":
            artists = item.get("artists", [])
            if artists:
                artist = f" by {artists[0]['name']}"

        # Play it
        if params.type in ("album", "playlist", "artist"):
            client.play(context_uri=uri)
        else:
            client.play(uri=uri)

        return f"Playing '{name}'{artist}"

    except PremiumRequiredError:
        return "Spotify Premium is required to control playback. I can still tell you what's playing."
    except NoActiveDeviceError as e:
        return f"No Spotify device available: {e}"
    except SpotifyError as e:
        return f"Spotify error: {e}"


def pause_music(params: PauseMusic) -> str:
    """Pause Spotify playback."""
    client = _get_client()

    if not client.configured:
        return "Spotify not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env"

    if not client.authenticated:
        return "Spotify not authenticated. Run 'uv run spotify-auth' to connect your account."

    try:
        client.pause()
        return "Playback paused"
    except PremiumRequiredError:
        return "Spotify Premium is required to control playback."
    except SpotifyError as e:
        return f"Spotify error: {e}"


def resume_music(params: ResumeMusic) -> str:
    """Resume Spotify playback."""
    client = _get_client()

    if not client.configured:
        return "Spotify not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env"

    if not client.authenticated:
        return "Spotify not authenticated. Run 'uv run spotify-auth' to connect your account."

    try:
        client.resume()
        return "Playback resumed"
    except PremiumRequiredError:
        return "Spotify Premium is required to control playback."
    except NoActiveDeviceError as e:
        return f"No Spotify device available: {e}"
    except SpotifyError as e:
        return f"Spotify error: {e}"


def skip_track(params: SkipTrack) -> str:
    """Skip to next track."""
    client = _get_client()

    if not client.configured:
        return "Spotify not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env"

    if not client.authenticated:
        return "Spotify not authenticated. Run 'uv run spotify-auth' to connect your account."

    try:
        client.skip()
        return "Skipped to next track"
    except PremiumRequiredError:
        return "Spotify Premium is required to control playback."
    except SpotifyError as e:
        return f"Spotify error: {e}"


def set_music_volume(params: SetMusicVolume) -> str:
    """Set Spotify volume."""
    client = _get_client()

    if not client.configured:
        return "Spotify not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env"

    if not client.authenticated:
        return "Spotify not authenticated. Run 'uv run spotify-auth' to connect your account."

    try:
        client.set_volume(params.volume)
        return f"Music volume set to {params.volume}%"
    except PremiumRequiredError:
        return "Spotify Premium is required to control playback."
    except SpotifyError as e:
        return f"Spotify error: {e}"


def get_playback_status(params: GetPlaybackStatus) -> str:
    """Get current playback status."""
    client = _get_client()

    if not client.configured:
        return "Spotify not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env"

    if not client.authenticated:
        return "Spotify not authenticated. Run 'uv run spotify-auth' to connect your account."

    try:
        state = client.get_playback_state()

        if not state or not state.track:
            return "Nothing is currently playing on Spotify."

        status = "Playing" if state.is_playing else "Paused"
        progress = _format_duration(state.progress_ms)
        duration = _format_duration(state.duration_ms)

        parts = [f"{status}: '{state.track}'"]
        if state.artist:
            parts.append(f"by {state.artist}")
        if state.album:
            parts.append(f"from '{state.album}'")
        parts.append(f"[{progress}/{duration}]")
        if state.volume is not None:
            parts.append(f"at {state.volume}% volume")

        return " ".join(parts)

    except SpotifyError as e:
        return f"Spotify error: {e}"


# ─── Dual Mode: CLI + Tool ─────────────────────────────────────────────────


def main() -> None:
    """CLI entry point with subcommands."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Spotify playback control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # play
    play_parser = subparsers.add_parser("play", help="Play music")
    play_parser.add_argument("query", help="Search query")
    play_parser.add_argument(
        "--type",
        default="track",
        choices=["track", "artist", "album", "playlist"],
        help="Content type to search",
    )

    # status
    subparsers.add_parser("status", help="Get playback status")

    # pause
    subparsers.add_parser("pause", help="Pause playback")

    # resume
    subparsers.add_parser("resume", help="Resume playback")

    # skip
    subparsers.add_parser("skip", help="Skip to next track")

    # volume
    vol_parser = subparsers.add_parser("volume", help="Set volume")
    vol_parser.add_argument("volume", type=int, help="Volume level 0-100")

    args = parser.parse_args()

    if args.command == "play":
        print(play_music(PlayMusic(query=args.query, type=args.type)))
    elif args.command == "status":
        print(get_playback_status(GetPlaybackStatus()))
    elif args.command == "pause":
        print(pause_music(PauseMusic()))
    elif args.command == "resume":
        print(resume_music(ResumeMusic()))
    elif args.command == "skip":
        print(skip_track(SkipTrack()))
    elif args.command == "volume":
        print(set_music_volume(SetMusicVolume(volume=args.volume)))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
else:
    from tools.base import tool

    tool(PlayMusic)(play_music)
    tool(PauseMusic)(pause_music)
    tool(ResumeMusic)(resume_music)
    tool(SkipTrack)(skip_track)
    tool(SetMusicVolume)(set_music_volume)
    tool(GetPlaybackStatus)(get_playback_status)
