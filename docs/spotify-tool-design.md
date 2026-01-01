# Spotify Music Tool Design

## Overview

Add voice-controlled Spotify playback to the home assistant. Playback control only—no library curation or playlist management.

**Supported commands:**
- "Play some jazz" / "Play Beatles" / "Play chill playlist"
- "What's playing?"
- "Pause" / "Resume" / "Skip" / "Next"
- "Turn the music down" / "Set music volume to 50"

## Constraints

| Constraint | Impact |
|------------|--------|
| Playback control requires Premium | Free users can only check what's playing |
| Requires active Spotify device | Auto-launch desktop app if needed |
| OAuth requires one-time browser auth | Initial setup opens browser |
| Tokens expire (1 hour) | Refresh tokens persisted locally |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  tools/spotify.py                                            │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ │
│  │ PlayMusic  │ │ PauseMusic │ │ResumeMusic │ │ SkipTrack  │ │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ │
│  ┌─────┴──────┐ ┌─────┴────────────────────────────┴───────┐ │
│  │SetMusic   │ │ GetPlaybackStatus                        │ │
│  │Volume     │ │ (track, artist, album, volume, state)    │ │
│  └─────┬──────┘ └─────┬────────────────────────────────────┘ │
│        └──────────────┘                                      │
│                 │                                            │
│                 ▼                                            │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   SpotifyClient                          │ │
│  │  - Token management (load/save/refresh)                  │ │
│  │  - Device management (find/launch)                       │ │
│  │  - API calls                                             │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
                    Spotify Web API
```

---

## Authentication

### Initial Setup (One-Time)

User runs a setup script that:

1. Opens browser to Spotify authorization URL
2. User logs in and grants permissions
3. Spotify redirects to local callback server (e.g., `http://localhost:8888/callback`)
4. Script exchanges auth code for access + refresh tokens
5. Tokens saved to `.spotify_token.json`

### Runtime Token Flow

```
Load tokens from file
        │
        ▼
   Token expired? ──No──► Use access token
        │
       Yes
        │
        ▼
  POST /api/token
  (with refresh_token)
        │
        ▼
  Save new tokens
        │
        ▼
  Use new access token
```

### Required Scopes

```
user-read-playback-state     # See what's playing, list devices
user-modify-playback-state   # Play/pause/skip/volume (Premium)
user-read-currently-playing  # Current track info
```

### Token Storage

```json
{
  "access_token": "BQD...",
  "refresh_token": "AQB...",
  "expires_at": 1704067200
}
```

**Location:** `.spotify_token.json` (gitignored)

---

## Device Management

### Problem

Spotify API controls remote devices—it doesn't play audio itself. Commands fail if no device is active.

### Strategy

Auto-launch Spotify desktop app transparently. Target only the local machine.

```
Check for active devices
        │
        ▼
  Device on this machine? ──Yes──► Use it
        │
       No
        │
        ▼
  Launch Spotify desktop app
        │
        ▼
  Poll for device (up to 10s)
        │
        ▼
  Found? ──Yes──► Use it
        │
       No
        │
        ▼
  Error: "Could not start Spotify"
```

### macOS Launch

```
open -a Spotify
```

(Linux/Windows support out of scope for now)

---

## Tool Commands

All playback controls require Premium. Info commands work for all users.

| Tool | Premium | Description | Example Voice Input |
|------|---------|-------------|---------------------|
| `PlayMusic` | Yes | Play track/artist/album/playlist by query | "Play some jazz" |
| `PauseMusic` | Yes | Pause playback | "Pause" |
| `ResumeMusic` | Yes | Resume playback | "Resume" |
| `SkipTrack` | Yes | Skip to next track | "Skip" / "Next" |
| `SetMusicVolume` | Yes | Adjust music/media volume (0-100) | "Turn the music down" |
| `GetPlaybackStatus` | No | Get current track, volume, play state | "What's playing?" |

### Volume Disambiguation

The assistant must determine intent:

| User Says | Intent | Action |
|-----------|--------|--------|
| "Turn the music down" | Media volume | `SetMusicVolume` |
| "Lower the volume on the song" | Media volume | `SetMusicVolume` |
| "Set device volume to 50" | System volume | `SetDeviceVolume` |
| "Turn down the speaker" | System volume | `SetDeviceVolume` |
| "How loud is the speaker?" | System volume | `GetDeviceVolume` |

**Note:** Device volume tools are implemented in `tools/device_volume.py` using macOS AppleScript.

### Tool Definitions

```
PlayMusic
├── query: str        # Search query (e.g., "chill jazz", "Beatles")
└── type: str         # "track", "artist", "album", "playlist" (default: "track")

SetMusicVolume
└── volume: int       # 0-100

PauseMusic, ResumeMusic, SkipTrack, GetPlaybackStatus
└── (no parameters)
```

### GetPlaybackStatus Response

Returns combined state in one call:

```json
{
  "is_playing": true,
  "track": "Bohemian Rhapsody",
  "artist": "Queen",
  "album": "A Night at the Opera",
  "volume": 65,
  "progress_ms": 124000,
  "duration_ms": 354000
}
```

Handles questions like:
- "What's playing?" → track/artist
- "How loud is the music?" → volume
- "Is anything playing?" → is_playing

---

## Premium Detection

### Approach

The API returns `403 Forbidden` with specific error when a Premium endpoint is called by a free user:

```json
{
  "error": {
    "status": 403,
    "message": "Player command failed: Premium required",
    "reason": "PREMIUM_REQUIRED"
  }
}
```

### Handling

1. Catch 403 on playback commands
2. Return friendly message: "Spotify Premium is required to control playback. I can still search for music or tell you what's playing."
3. Optionally cache premium status to avoid repeated failures

---

## File Structure

```
home-assistant/
├── tools/
│   ├── spotify.py           # Tool definitions (@tool decorated)
│   └── __init__.py          # Add: from tools import spotify
├── spotify/
│   ├── __init__.py
│   ├── client.py            # SpotifyClient class
│   ├── auth.py              # Token management
│   └── setup.py             # One-time auth script
├── .spotify_token.json      # Token storage (gitignored)
└── .env                     # Add SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SPOTIFY_CLIENT_ID` | From Spotify Developer Dashboard |
| `SPOTIFY_CLIENT_SECRET` | From Spotify Developer Dashboard |
| `SPOTIFY_REDIRECT_URI` | Default: `http://localhost:8888/callback` |

---

## Implementation Steps

### Phase 1: Setup & Auth

1. Register app at developer.spotify.com
2. Add client ID/secret to `.env`
3. Create `spotify/auth.py` - token load/save/refresh
4. Create `spotify/setup.py` - one-time OAuth flow with local callback server
5. Add `.spotify_token.json` to `.gitignore`

### Phase 2: Client

1. Create `spotify/client.py` with:
   - `__init__`: Load tokens, setup session
   - `_request`: Generic API call with auto-refresh
   - `_ensure_device`: Device check/launch logic
   - API methods: `search`, `play`, `pause`, `skip`, `get_current`, `get_devices`

### Phase 3: Tools

1. Create `tools/spotify.py` with Pydantic models and handlers
2. Register in `tools/__init__.py`
3. Handle Premium-required errors gracefully

### Phase 4: Polish

1. Test with Premium account
2. Test with free account (verify graceful degradation)
3. Test cold start (no Spotify running)
4. Add to README

---

## Example Interactions

**"Play some chill music"**
→ Search for "chill music" playlists → Play first result
→ "Playing 'Chill Hits' playlist"

**"Play Bohemian Rhapsody"**
→ Search for track → Play
→ "Playing 'Bohemian Rhapsody' by Queen"

**"What's playing?"**
→ `GetPlaybackStatus` → "Playing 'Karma Police' by Radiohead at 65% volume"

**"Is music playing?"**
→ `GetPlaybackStatus` → "Yes, 'Karma Police' by Radiohead - about 2 minutes in"

**"Skip" / "Pause" / "Resume"**
→ Execute command → Confirm action

**Free user tries playback command**
→ 403 error → "This requires Spotify Premium"

---

## Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing
    "httpx",  # For async-friendly HTTP (or use requests)
]
```

No Spotify SDK needed—direct REST API calls are simpler.

---

## Design Decisions

- **Auto-launch:** Yes, transparently launch Spotify desktop app if not running
- **Device:** Desktop player only (local machine speaker)
- **Scope:** Playback interface only—no queue management, no playlist creation
- **Philosophy:** Control what's playing, not curate libraries

---

## Security Notes

- Never log access/refresh tokens
- `.spotify_token.json` must be gitignored
- Client secret stays server-side (in `.env`, never in responses)
