"""In-memory operation log and Fusion timeline formatter for TimberLine."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple


@dataclass(frozen=True)
class OperationEntry:
    timestamp: str
    command: str
    details: str


class OperationLog:
    """Tracks TimberLine woodworking operations performed in the current session."""

    def __init__(self) -> None:
        self._entries: List[OperationEntry] = []

    def record(self, command: str, details: str) -> OperationEntry:
        entry = OperationEntry(
            timestamp=datetime.now().strftime("%H:%M:%S"),
            command=command,
            details=details,
        )
        self._entries.append(entry)
        return entry

    def entries(self) -> List[OperationEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def format_report(
        self, timeline_items: List[Tuple[str, bool]] | None = None
    ) -> str:
        lines: List[str] = ["=== TimberLine Operations ==="]
        if not self._entries:
            lines.append("  (No TimberLine operations recorded yet in this session.)")
        else:
            for idx, entry in enumerate(self._entries, 1):
                lines.append(
                    f"  {idx}. [{entry.timestamp}] {entry.command}: {entry.details}"
                )

        if timeline_items is not None:
            lines.append("")
            lines.append("=== Fusion Design Timeline ===")
            if not timeline_items:
                lines.append("  (Timeline is empty.)")
            else:
                for idx, (name, is_suppressed) in enumerate(timeline_items, 1):
                    suffix = " [suppressed]" if is_suppressed else ""
                    lines.append(f"  {idx}. {name}{suffix}")

        return "\n".join(lines)


SESSION_LOG = OperationLog()
