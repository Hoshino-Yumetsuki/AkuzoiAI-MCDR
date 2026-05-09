from __future__ import annotations

import threading

from mcdreforged.api.all import CommandSource, ServerInterface
from mcdreforged.utils.types.message import MessageText

# Custom MCDR CommandSource that captures command output.
class InterceptingCommandSource(CommandSource):
    # Synthetic CommandSource that captures command output.

    def __init__(self, permission_level: int) -> None:
        self._permission_level = permission_level
        self._buffer: list[str] = []
        self._lock = threading.Lock()

    def get_server(self) -> ServerInterface:
        return ServerInterface.si()

    def get_permission_level(self) -> int:
        return self._permission_level

    def reply(self, message: MessageText, **kwargs) -> None:  # type: ignore[override]
        with self._lock:
            self._buffer.append(str(message))

    @property
    def is_player(self) -> bool:
        return False

    @property
    def is_console(self) -> bool:
        return False

    def get_output(self) -> str:
        with self._lock:
            if not self._buffer:
                return "(no output)"
            return "\n".join(self._buffer)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
