"""Structural adapter interface; adapters may use different in-memory documents."""
from typing import Any, Protocol
from pathlib import Path
class Adapter(Protocol):
    name: str
    build: str
    def open(self, path: Path) -> Any: ...
    def save(self, opened: Any, path: Path, format: str, version: str, encoding: str) -> None: ...
