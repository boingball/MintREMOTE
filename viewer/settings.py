"""Small per-user preference file; invalid/unwritable settings never block the client."""
from __future__ import annotations

import json
import os
from pathlib import Path

SCALES = ("Fit", "1x", "2x", "3x", "4x")


def settings_path() -> Path:
    base = Path(os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
                or Path.home() / ".config")
    return base / "MintREMOTE" / "settings.json"


def load_settings(path: Path | None = None) -> dict:
    try:
        data = json.loads((path or settings_path()).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        result = {}
        if isinstance(data.get("host"), str):
            result["host"] = data["host"][:255]
        port = data.get("port")
        if isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535:
            result["port"] = port
        if data.get("scale") in SCALES:
            result["scale"] = data["scale"]
        return result
    except (OSError, ValueError, TypeError):
        return {}


def save_settings(host: str, port: int, scale: str, path: Path | None = None) -> None:
    target = path or settings_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps({"host": host, "port": port, "scale": scale}),
                             encoding="utf-8")
        temporary.replace(target)
    except OSError:
        pass
