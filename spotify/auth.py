"""Spotify OAuth token management."""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

TOKEN_FILE = Path(".spotify_token.json")
TOKEN_URL = "https://accounts.spotify.com/api/token"


@dataclass
class Tokens:
    """OAuth tokens with expiry."""

    access_token: str
    refresh_token: str
    expires_at: float

    @property
    def expired(self) -> bool:
        """Check if access token is expired (with 60s buffer)."""
        return time.time() >= (self.expires_at - 60)


class TokenManager:
    """Manages Spotify OAuth tokens."""

    def __init__(self) -> None:
        self.client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
        self.client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
        self._tokens: Tokens | None = None

    @property
    def configured(self) -> bool:
        """Check if Spotify credentials are configured."""
        return bool(self.client_id and self.client_secret)

    def load(self) -> Tokens | None:
        """Load tokens from file."""
        if self._tokens:
            return self._tokens

        if not TOKEN_FILE.exists():
            return None

        try:
            data = json.loads(TOKEN_FILE.read_text())
            self._tokens = Tokens(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=data["expires_at"],
            )
            return self._tokens
        except (json.JSONDecodeError, KeyError):
            return None

    def save(self, tokens: Tokens) -> None:
        """Save tokens to file."""
        self._tokens = tokens
        TOKEN_FILE.write_text(
            json.dumps(
                {
                    "access_token": tokens.access_token,
                    "refresh_token": tokens.refresh_token,
                    "expires_at": tokens.expires_at,
                },
                indent=2,
            )
        )

    def refresh(self) -> Tokens | None:
        """Refresh the access token using refresh token."""
        tokens = self.load()
        if not tokens:
            return None

        if not self.configured:
            return None

        try:
            response = httpx.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": tokens.refresh_token,
                },
                auth=(self.client_id, self.client_secret),
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            new_tokens = Tokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", tokens.refresh_token),
                expires_at=time.time() + data["expires_in"],
            )
            self.save(new_tokens)
            return new_tokens

        except httpx.HTTPError:
            return None

    def get_valid_token(self) -> str | None:
        """Get a valid access token, refreshing if needed."""
        tokens = self.load()
        if not tokens:
            return None

        if tokens.expired:
            tokens = self.refresh()
            if not tokens:
                return None

        return tokens.access_token

    def exchange_code(self, code: str, redirect_uri: str) -> Tokens | None:
        """Exchange authorization code for tokens."""
        if not self.configured:
            return None

        try:
            response = httpx.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                auth=(self.client_id, self.client_secret),
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            tokens = Tokens(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=time.time() + data["expires_in"],
            )
            self.save(tokens)
            return tokens

        except httpx.HTTPError:
            return None
