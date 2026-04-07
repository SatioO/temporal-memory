import threading
import time
import hashlib
import json
from typing import Dict

from dataclasses import dataclass

TTL_MS = 5 * 60 * 1000
CLEANUP_INTERVAL_MS = 60_000


@dataclass
class DedupEntry:
    hash: str
    expires_at: float


class DedupMap:
    def __init__(self):
        self.entries: Dict[str, DedupEntry] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self.cleanup_thread = threading.Thread(
            target=self._run_cleanup, daemon=True)
        self.cleanup_thread.start()  # fix: thread was created but never started — stop() would raise RuntimeError("cannot join thread before it is started")

    def compute_hash(self, session_id: str, tool_name: str, tool_input) -> str:
        if isinstance(tool_input, str):
            input_str = tool_input[:500]
        else:
            input_str = json.dumps(tool_input or "")[:500]

        raw = f"{session_id}:{tool_name}:{input_str}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def is_duplicate(self, hash_value: str) -> bool:
        with self._lock:
            entry = self.entries.get(hash_value)
            if not entry:
                return False

            if time.time() * 1000 > entry.expires_at:
                del self.entries[hash_value]
                return False

            return True

    def record(self, hash_value: str) -> None:
        expires_at = time.time() * 1000 + TTL_MS
        with self._lock:
            self.entries[hash_value] = DedupEntry(hash=hash_value, expires_at=expires_at)

    def _run_cleanup(self):
        while not self._stop_event.is_set():
            time.sleep(CLEANUP_INTERVAL_MS / 1000)
            self.cleanup()

    def cleanup(self):
        now = time.time() * 1000
        with self._lock:
            expired_keys = [k for k, v in self.entries.items()
                            if now > v.expires_at]
            for k in expired_keys:
                del self.entries[k]

    def stop(self):
        self._stop_event.set()
        self.cleanup_thread.join(timeout=2)  # fix: no timeout meant stop() could block for up to CLEANUP_INTERVAL_MS (60s) while thread sleeps
