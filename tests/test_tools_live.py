#!/usr/bin/env python3
"""Live integration tests for tools.

Run: uv run pytest tests/ -v
"""

import os
import pytest

from tools.weather import GetWeather, get_weather
from tools.news import GetNews, get_news
from tools.search import SearchInternet, search_internet
from tools.device_volume import (
    GetDeviceVolume, get_device_volume,
    SetDeviceVolume, set_device_volume,
)
from tools.history import GetHistory, get_history
from tools.timer import (
    SetTimer, set_timer_handler,
    ListTimers, list_timers_handler,
    CancelTimer, cancel_timer_handler,
    EditTimer, edit_timer_handler,
)


class TestWeather:
    """Live weather API tests."""

    def test_weather_with_location(self):
        result = get_weather(GetWeather(location="New York"))
        assert "New York" in result
        assert "°F" in result
        assert any(word in result.lower() for word in ["clear", "cloud", "rain", "snow", "fog", "storm"])

    def test_weather_default_location(self):
        result = get_weather(GetWeather())
        assert "°F" in result
        # Should resolve to some location via IP

    def test_weather_invalid_location(self):
        result = get_weather(GetWeather(location="zzzznotarealplace12345"))
        assert "not found" in result.lower()

    def test_weather_international(self):
        result = get_weather(GetWeather(location="Tokyo"))
        assert "Tokyo" in result or "Japan" in result
        assert "°F" in result


class TestNews:
    """Live news API tests."""

    def test_news_returns_articles(self):
        result = get_news(GetNews())
        assert "articles" in result.lower() or "ARTICLES" in result
        # Should have numbered items
        assert "1." in result or "[1]" in result

    def test_news_has_sections(self):
        result = get_news(GetNews())
        # BBC API returns sections like Latest, World, etc.
        assert any(section in result for section in ["Latest", "World", "Business", "Technology"])


class TestSearch:
    """Live Perplexity search tests."""

    @pytest.fixture(autouse=True)
    def check_api_key(self):
        if not os.environ.get("PERPLEXITY_API_KEY"):
            pytest.skip("PERPLEXITY_API_KEY not set")

    def test_search_simple_query(self):
        result = search_internet(SearchInternet(query="What is Python programming language?"))
        assert len(result) > 50
        assert "python" in result.lower()

    def test_search_current_events(self):
        result = search_internet(SearchInternet(query="Latest tech news today"))
        assert len(result) > 50
        # Should return something substantive
        assert not result.startswith("Error")


class TestDeviceVolume:
    """Live macOS volume tests."""

    @pytest.fixture(autouse=True)
    def check_macos(self):
        import platform
        if platform.system() != "Darwin":
            pytest.skip("macOS only")

    def test_get_volume(self):
        result = get_device_volume(GetDeviceVolume())
        assert "%" in result
        assert "volume" in result.lower()

    def test_set_and_restore_volume(self):
        # Get current volume
        current = get_device_volume(GetDeviceVolume())

        # Extract current level
        import re
        match = re.search(r"(\d+)%", current)
        original_volume = int(match.group(1)) if match else 50

        # Set to test value
        test_volume = 25 if original_volume != 25 else 30
        set_result = set_device_volume(SetDeviceVolume(volume=test_volume))
        assert f"{test_volume}%" in set_result

        # Verify it changed
        verify = get_device_volume(GetDeviceVolume())
        assert f"{test_volume}%" in verify

        # Restore original
        set_device_volume(SetDeviceVolume(volume=original_volume))

    def test_volume_boundaries(self):
        # Get current to restore later
        current = get_device_volume(GetDeviceVolume())
        import re
        match = re.search(r"(\d+)%", current)
        original = int(match.group(1)) if match else 50

        # Test min
        result = set_device_volume(SetDeviceVolume(volume=0))
        assert "0%" in result

        # Test max
        result = set_device_volume(SetDeviceVolume(volume=100))
        assert "100%" in result

        # Restore
        set_device_volume(SetDeviceVolume(volume=original))


class TestHistory:
    """History tool tests."""

    def test_history_empty_or_returns(self):
        result = get_history(GetHistory(limit=5))
        # Either has history or says none available
        assert "history" in result.lower() or "User:" in result

    def test_history_search(self):
        result = get_history(GetHistory(query="weather", limit=3))
        # Either finds matches or says none found
        assert "weather" in result.lower() or "not found" in result.lower() or "No past" in result


class TestCLI:
    """CLI integration tests."""

    def test_weather_cli(self):
        import subprocess
        result = subprocess.run(
            ["uv", "run", "weather", "--location", "Paris"],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0
        assert "Paris" in result.stdout or "France" in result.stdout

    def test_news_cli(self):
        import subprocess
        result = subprocess.run(
            ["uv", "run", "news"],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0
        assert "1." in result.stdout or "[1]" in result.stdout

    def test_volume_cli(self):
        import subprocess
        import platform
        if platform.system() != "Darwin":
            pytest.skip("macOS only")

        result = subprocess.run(
            ["uv", "run", "volume"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "%" in result.stdout

    def test_search_cli_no_key(self):
        import subprocess
        # Run without PERPLEXITY_API_KEY to test error handling
        env = os.environ.copy()
        env.pop("PERPLEXITY_API_KEY", None)

        result = subprocess.run(
            ["uv", "run", "search", "test query"],
            capture_output=True, text=True, timeout=10,
            env=env
        )
        assert result.returncode == 0
        assert "unavailable" in result.stdout.lower() or "not configured" in result.stdout.lower()


class TestTimer:
    """Timer tool tests."""

    def test_create_timer_duration(self):
        result = set_timer_handler(SetTimer(time="1h", label="test_duration"))
        assert "test_duration" in result
        assert "set for" in result.lower()
        # Clean up
        cancel_timer_handler(CancelTimer(identifier="test_duration"))

    def test_create_timer_with_minutes(self):
        result = set_timer_handler(SetTimer(time="30m", label="test_minutes"))
        assert "test_minutes" in result
        assert "30m" in result or "29m" in result  # May be slightly less due to timing
        cancel_timer_handler(CancelTimer(identifier="test_minutes"))

    def test_create_alarm_time(self):
        result = set_timer_handler(SetTimer(time="11:59pm", label="test_alarm"))
        assert "test_alarm" in result
        assert "11:59 PM" in result
        cancel_timer_handler(CancelTimer(identifier="test_alarm"))

    def test_list_timers(self):
        # Create a timer
        set_timer_handler(SetTimer(time="2h", label="list_test"))

        result = list_timers_handler(ListTimers())
        assert "list_test" in result

        # Clean up
        cancel_timer_handler(CancelTimer(identifier="list_test"))

    def test_list_timers_empty(self):
        # Ensure no timers exist (clean state)
        result = list_timers_handler(ListTimers())
        # Either shows timers or says none
        assert "No active timers" in result or "•" in result

    def test_cancel_timer_by_label(self):
        set_timer_handler(SetTimer(time="1h", label="cancel_test"))
        result = cancel_timer_handler(CancelTimer(identifier="cancel_test"))
        assert "cancelled" in result.lower()
        assert "cancel_test" in result

    def test_cancel_timer_not_found(self):
        result = cancel_timer_handler(CancelTimer(identifier="nonexistent_timer_xyz"))
        assert "no timer found" in result.lower()

    def test_edit_timer(self):
        set_timer_handler(SetTimer(time="1h", label="edit_test"))
        result = edit_timer_handler(EditTimer(identifier="edit_test", new_time="2h"))
        assert "updated" in result.lower()
        assert "edit_test" in result
        cancel_timer_handler(CancelTimer(identifier="edit_test"))

    def test_invalid_time_format(self):
        result = set_timer_handler(SetTimer(time="invalid"))
        assert "cannot parse" in result.lower()

    def test_timer_cli_create(self):
        import subprocess
        result = subprocess.run(
            ["uv", "run", "timer", "1h", "--label", "cli_test"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert "cli_test" in result.stdout

        # Clean up
        subprocess.run(["uv", "run", "timer", "--cancel", "cli_test"], timeout=10)

    def test_timer_cli_list(self):
        import subprocess
        result = subprocess.run(
            ["uv", "run", "timer", "--list"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
