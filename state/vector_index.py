import base64
import heapq
import json
import math
import struct
from typing import Dict, List, Tuple


def float32_to_base64(arr: List[float]) -> str:
    # pack floats into bytes (float32)
    byte_data = struct.pack(f"{len(arr)}f", *arr)
    return base64.b64encode(byte_data).decode("utf-8")


def base64_to_float32(b64: str) -> List[float]:
    byte_data = base64.b64decode(b64.encode("utf-8"))
    count = len(byte_data) // 4
    return list(struct.unpack(f"{count}f", byte_data))


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a)
    norm_b = sum(x * x for x in b)

    denom = math.sqrt(norm_a * norm_b)  # one sqrt instead of two
    return 0.0 if denom == 0 else dot / denom


class VectorIndex:
    def __init__(self):
        self.vectors: Dict[str, Dict[str, object]] = {}

    def add(self, obs_id: str, session_id: str, embedding: List[float]) -> None:
        self.vectors[obs_id] = {
            "embedding": embedding,
            "session_id": session_id,
        }

    def remove(self, obs_id: str) -> None:
        self.vectors.pop(obs_id, None)

    def search(
        self, query: List[float], limit: int = 20
    ) -> List[Dict[str, object]]:
        # heapq.nlargest is O(n log k) vs a full sort at O(n log n)
        scored = (
            {
                "obs_id": obs_id,
                "session_id": entry["session_id"],
                "score": cosine_similarity(query, entry["embedding"]),
            }
            for obs_id, entry in self.vectors.items()
        )
        return heapq.nlargest(limit, scored, key=lambda x: x["score"])

    @property
    def size(self) -> int:
        return len(self.vectors)

    def clear(self) -> None:
        self.vectors.clear()

    def serialize(self) -> str:
        data: List[Tuple[str, Dict[str, str]]] = []

        for obs_id, entry in self.vectors.items():
            data.append(
                (
                    obs_id,
                    {
                        "embedding": float32_to_base64(entry["embedding"]),
                        "session_id": entry["session_id"],
                    },
                )
            )

        return json.dumps(data)

    @staticmethod
    def deserialize(json_str: str) -> "VectorIndex":
        idx = VectorIndex()
        data = json.loads(json_str)

        for obs_id, entry in data:
            idx.vectors[obs_id] = {
                "embedding": base64_to_float32(entry["embedding"]),
                "session_id": entry["session_id"],
            }

        return idx
