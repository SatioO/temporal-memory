import time
import uuid


class KV:
    sessions = "mem:sessions"
    profiles = "mem:profiles"
    memories = "mem:memories"

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
