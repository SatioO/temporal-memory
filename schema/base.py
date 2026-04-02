import dataclasses
import json
from enum import Enum
from typing import Any, Self, Union, get_args, get_origin, get_type_hints


def to_primitive(obj: Any) -> Any:
    """Recursively convert dataclass/Enum instances to JSON-safe primitives."""
    if isinstance(obj, Enum):
        return obj.value
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_primitive(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, list):
        return [to_primitive(i) for i in obj]
    if isinstance(obj, dict):
        return {k: to_primitive(v) for k, v in obj.items()}
    return obj


def _coerce(annotation: Any, value: Any) -> Any:
    """Coerce *value* to match *annotation*, handling Optional/list/Enum/nested Model."""
    if annotation is Any or value is None:
        return value

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Optional[T] == Union[T, None]
    if origin is Union:
        non_none = [a for a in args if a is not type(None)]
        return _coerce(non_none[0], value) if len(non_none) == 1 else value

    # list[T]
    if origin is list:
        item_type = args[0] if args else Any
        return [_coerce(item_type, item) for item in value]

    # Literal and other complex origins — pass through unchanged
    if not isinstance(annotation, type):
        return value

    # Enum
    if issubclass(annotation, Enum):
        return annotation(value) if not isinstance(value, annotation) else value

    # Nested Model / dataclass
    if dataclasses.is_dataclass(annotation) and isinstance(value, dict):
        return annotation.from_dict(value)  # type: ignore[attr-defined]

    return value


class Model:
    @classmethod
    def from_dict(cls, data: dict) -> Self:
        hints = get_type_hints(cls)
        kwargs: dict[str, Any] = {}
        for f in dataclasses.fields(cls):  # type: ignore[arg-type]
            if f.name not in data:
                continue  # let dataclass apply its default
            kwargs[f.name] = _coerce(hints.get(f.name, Any), data[f.name])
        return cls(**kwargs)

    def to_dict(self) -> dict:
        return to_primitive(self)  # type: ignore[arg-type]

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
