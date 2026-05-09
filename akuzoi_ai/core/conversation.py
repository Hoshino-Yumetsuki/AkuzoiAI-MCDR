from __future__ import annotations

import threading
from typing import List

from haystack.dataclasses import ChatMessage


class ConversationWindow:
    def __init__(self, max_messages: int = 20) -> None:
        if max_messages < 2:
            max_messages = 2
        self._max = max_messages if max_messages % 2 == 0 else max_messages - 1
        self._history: List[ChatMessage] = []
        self._lock = threading.Lock()

    def get(self) -> List[ChatMessage]:
        with self._lock:
            return list(self._history)

    def add(self, human_text: str, ai_text: str) -> None:
        with self._lock:
            self._history.append(ChatMessage.from_user(human_text))
            self._history.append(ChatMessage.from_assistant(ai_text))
            self._trim()

    def clear(self) -> None:
        with self._lock:
            self._history.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._history)

    def _trim(self) -> None:
        while len(self._history) > self._max:
            self._history = self._history[2:]
