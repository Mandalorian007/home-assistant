#!/usr/bin/env python3
"""One-time Spotify OAuth setup.

Run: uv run spotify-auth

Opens browser for authorization, handles callback, saves tokens.
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

load_dotenv()

# OAuth configuration
SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
]
DEFAULT_REDIRECT_URI = "http://localhost:8888/callback"


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback."""

    auth_code: str | None = None

    def do_GET(self) -> None:
        """Handle callback GET request."""
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            query = parse_qs(parsed.query)

            if "error" in query:
                self.send_error_page(query["error"][0])
                CallbackHandler.auth_code = None
            elif "code" in query:
                CallbackHandler.auth_code = query["code"][0]
                self.send_success_page()
            else:
                self.send_error_page("No code received")
        else:
            self.send_response(404)
            self.end_headers()

    def send_success_page(self) -> None:
        """Send success HTML page."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"""
            <html>
            <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
            </body>
            </html>
        """)

    def send_error_page(self, error: str) -> None:
        """Send error HTML page."""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(f"""
            <html>
            <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1>Authorization Failed</h1>
                <p>Error: {error}</p>
            </body>
            </html>
        """.encode())

    def log_message(self, format: str, *args) -> None:
        """Suppress request logging."""
        pass


def get_auth_url(client_id: str, redirect_uri: str) -> str:
    """Build Spotify authorization URL."""
    scope = " ".join(SCOPES)
    return (
        "https://accounts.spotify.com/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
    )


def main() -> None:
    """Run OAuth setup flow."""
    from spotify.auth import TokenManager

    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", DEFAULT_REDIRECT_URI)

    if not client_id or not client_secret:
        print("Error: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in .env")
        print("\nTo set up Spotify:")
        print("1. Go to https://developer.spotify.com/dashboard")
        print("2. Create an app")
        print("3. Add redirect URI: http://localhost:8888/callback")
        print("4. Copy Client ID and Client Secret to .env")
        sys.exit(1)

    # Check if already authenticated
    token_manager = TokenManager()
    if token_manager.get_valid_token():
        print("Already authenticated with Spotify.")
        response = input("Re-authenticate? [y/N]: ").strip().lower()
        if response != "y":
            print("Keeping existing authentication.")
            return

    # Parse redirect URI for server
    parsed = urlparse(redirect_uri)
    port = parsed.port or 8888

    # Start callback server
    server = HTTPServer(("localhost", port), CallbackHandler)
    server.timeout = 120  # 2 minute timeout

    # Open browser
    auth_url = get_auth_url(client_id, redirect_uri)
    print(f"\nOpening browser for Spotify authorization...")
    print(f"If browser doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Wait for callback
    print("Waiting for authorization...")
    server.handle_request()

    if not CallbackHandler.auth_code:
        print("Authorization failed or cancelled.")
        sys.exit(1)

    # Exchange code for tokens
    print("Exchanging code for tokens...")
    tokens = token_manager.exchange_code(CallbackHandler.auth_code, redirect_uri)

    if tokens:
        print("\nSpotify authentication successful!")
        print("You can now use Spotify commands with the assistant.")
    else:
        print("\nFailed to exchange authorization code.")
        sys.exit(1)


if __name__ == "__main__":
    main()
