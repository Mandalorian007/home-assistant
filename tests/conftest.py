"""Pytest configuration - load .env before tests."""

from dotenv import load_dotenv

# Load .env file for API keys
load_dotenv()
