"""Device volume control using macOS AppleScript."""

import subprocess
from pydantic import BaseModel, Field
from tools.base import tool


def _run_applescript(script: str) -> str:
    """Run AppleScript and return output."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


def _get_volume_state() -> dict:
    """Get current volume and mute state."""
    script = "get volume settings"
    output = _run_applescript(script)
    # Output: "output volume:50, input volume:75, alert volume:100, output muted:false"
    state = {}
    for part in output.split(", "):
        key, value = part.split(":")
        key = key.strip().replace(" ", "_")
        value = value.strip()
        if value in ("true", "false"):
            state[key] = value == "true"
        else:
            state[key] = int(value)
    return state


class GetDeviceVolume(BaseModel):
    """Get the current device speaker volume and mute status."""

    pass


@tool(GetDeviceVolume)
def get_device_volume(params: GetDeviceVolume) -> str:
    """Get current macOS system volume."""
    try:
        state = _get_volume_state()
        volume = state.get("output_volume", 0)
        muted = state.get("output_muted", False)

        if muted:
            return f"Device volume is muted (level set to {volume}%)"
        return f"Device volume is at {volume}%"

    except Exception as e:
        return f"Error getting device volume: {e}"


class SetDeviceVolume(BaseModel):
    """Set the device speaker volume. Use this for system/device volume, not music volume."""

    volume: int = Field(
        description="Volume level from 0 to 100",
        ge=0,
        le=100,
    )


@tool(SetDeviceVolume)
def set_device_volume(params: SetDeviceVolume) -> str:
    """Set macOS system volume."""
    try:
        script = f"set volume output volume {params.volume}"
        _run_applescript(script)

        if params.volume == 0:
            return "Device volume set to 0% (silent)"
        return f"Device volume set to {params.volume}%"

    except Exception as e:
        return f"Error setting device volume: {e}"
