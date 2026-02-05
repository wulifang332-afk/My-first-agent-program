"""Structured tracing utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional


@dataclass
class TraceLogger:
    path: str
    enabled: bool = True
    _buffer: list[Dict[str, Any]] = field(default_factory=list)

    def log(self, event: str, payload: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "payload": payload or {},
        }
        self._buffer.append(entry)

    def extend(self, entries: Iterable[Dict[str, Any]]) -> None:
        if not self.enabled:
            return
        for entry in entries:
            self._buffer.append(entry)

    def flush(self) -> None:
        if not self.enabled:
            return
        with open(self.path, "w", encoding="utf-8") as handle:
            for entry in self._buffer:
                handle.write(json.dumps(entry))
                handle.write("\n")
