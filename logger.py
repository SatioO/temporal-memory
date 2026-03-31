import logging
import os

_LOG_LEVEL = os.environ.get("GRAPHMIND_LOG_LEVEL", "INFO").upper()

_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter(
    fmt="%(asctime)s [graphmind] %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
))

_root = logging.getLogger("graphmind")
_root.setLevel(_LOG_LEVEL)
_root.addHandler(_handler)
_root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"graphmind.{name}")
