from __future__ import annotations

import threading
from typing import FrozenSet, Set


# Player tracker for online player
class PlayerTracker:
    def __init__(self) -> None:
        self._players: Set[str] = set()
        self._lock = threading.Lock()

    def on_player_joined(self, player: str) -> None:
        with self._lock:
            self._players.add(player)

    def on_player_left(self, player: str) -> None:
        with self._lock:
            self._players.discard(player)

    def get_online_players(self) -> FrozenSet[str]:
        with self._lock:
            return frozenset(self._players)

    def clear(self) -> None:
        with self._lock:
            self._players.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._players)
