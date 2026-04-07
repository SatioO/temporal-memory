from dataclasses import dataclass
import datetime
import re
import time
from typing import Callable
import uuid


@dataclass(frozen=True)
class Stream:
    name: str
    group: Callable[[str], str]


STREAM = Stream(
    name="mem-live",
    group=lambda session_id: session_id,
)


class KV:
    sessions = "mem:sessions"
    profiles = "mem:profiles"
    memories = "mem:memories"
    summaries = "mem:summaries"

    @staticmethod
    def observations(session_id: str) -> str:
        return f"mem:obs:{session_id}"

    @staticmethod
    def embeddings(obs_id: str) -> str:
        return f"mem:emb:{obs_id}"


def generate_id(prefix: str):
    ts = base36_encode(int(time.time() * 1000))
    rand = uuid.uuid4().hex[:12]

    return f"{prefix}_{ts}_{rand}"


def base36_encode(number: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if number == 0:
        return "0"

    result = []
    while number:
        number, rem = divmod(number, 36)
        result.append(chars[rem])

    return "".join(reversed(result))


def jaccard_similarity(a: str, b: str) -> float:
    set_a = {t for t in re.split(r"\s+", a) if len(t) > 2}
    set_b = {t for t in re.split(r"\s+", b) if len(t) > 2}

    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0

    intersection = sum(1 for word in set_a if word in set_b)

    return intersection / (len(set_a) + len(set_b) - intersection)


def parse_ts(ts: str) -> int:
    # fix: was datetime.fromisoformat — datetime is the module, not the class
    return int(datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
