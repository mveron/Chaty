from collections import defaultdict
from threading import Lock

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


class SessionStore:
    def __init__(self, max_messages: int = 10) -> None:
        self._messages: dict[str, list[BaseMessage]] = defaultdict(list)
        self._max_messages = max_messages
        self._lock = Lock()

    def get_messages(self, session_id: str) -> list[BaseMessage]:
        with self._lock:
            return list(self._messages[session_id])

    def append_turn(self, session_id: str, user_message: str, assistant_message: str) -> None:
        with self._lock:
            self._messages[session_id].append(HumanMessage(content=user_message))
            self._messages[session_id].append(AIMessage(content=assistant_message))
            self._messages[session_id] = self._messages[session_id][-self._max_messages :]


session_store = SessionStore()
