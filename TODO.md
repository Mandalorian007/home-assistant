Done! I've built out the Spotify tool following the design doc. Here's what was created:

  New Files:
  - spotify/auth.py - Token management (load/save/refresh)
  - spotify/client.py - Spotify Web API client with device management
  - spotify/setup.py - One-time OAuth setup script
  - tools/spotify.py - 6 tools: PlayMusic, PauseMusic, ResumeMusic, SkipTrack, SetMusicVolume, GetPlaybackStatus
  - tests/test_spotify.py - Integration tests

  CLI Commands:
  uv run spotify play "chill jazz"     # Play music
  uv run spotify status                # What's playing
  uv run spotify pause                 # Pause
  uv run spotify resume                # Resume
  uv run spotify skip                  # Next track
  uv run spotify volume 50             # Set volume

  ---
  Authentication Setup

  Step 1: Create a Spotify App

  1. Go to https://developer.spotify.com/dashboard
  2. Click Create App
  3. Fill in:
    - App name: Home Assistant (or whatever you like)
    - App description: anything
    - Redirect URI: http://localhost:8888/callback
  4. Check the Web API box
  5. Click Save
  6. Click Settings → copy your Client ID and Client Secret

  Step 2: Add Credentials to .env

  # Add to .env
  SPOTIFY_CLIENT_ID=your_client_id_here
  SPOTIFY_CLIENT_SECRET=your_client_secret_here

  Step 3: Authenticate

  uv run spotify-auth

  This opens your browser to authorize the app. After granting access, tokens are saved to .spotify_token.json (gitignored).

  Step 4: Test

  uv run spotify status

  Note: Playback control requires Spotify Premium. Free users can only check what's playing.






CRITICAL NOTE: Spotify currently has new apps blocked for creation in dashboard and news should be checked to unblock and finish integration. 