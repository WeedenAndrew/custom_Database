import json
import math
import time
from typing import Any, Callable

from nitric.exception import NotFoundException
from nitric.resources import kv


custom_database = kv("custom-database").allow("get", "set", "delete")


def _validate_name(value: Any, maximum: int, label: str) -> None:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError(f"{label} must be a non-empty string of at most {maximum} characters")


def _validate_ttl(value: Any) -> None:
    if type(value) not in (int, float) or value <= 0:
        raise ValueError("ttl must be a positive finite number")
    if type(value) is float and not math.isfinite(value):
        raise ValueError("ttl must be a positive finite number")


def _encode(value: Any) -> str:
    nodes: list[Any] = [None]
    active: set[int] = set()
    stack = [(False, value, 0)]

    while stack:
        exiting, current, index = stack.pop()
        if exiting:
            active.remove(id(current))
            continue

        kind = type(current)
        if kind is str:
            nodes[index] = ["str", current]
        elif kind is bool:
            nodes[index] = ["bool", current]
        elif kind is int:
            nodes[index] = ["int", str(current)]
        elif kind is float:
            if not math.isfinite(current):
                raise ValueError("values must not contain NaN or infinity")
            nodes[index] = ["float", repr(current)]
        elif kind in (list, dict):
            identity = id(current)
            if identity in active:
                raise ValueError("cyclic values are not supported")
            active.add(identity)
            stack.append((True, current, index))
            children = []
            references = []

            if kind is dict:
                for key, item in current.items():
                    if not isinstance(key, str):
                        raise ValueError("dictionary keys must be strings")
                    child_index = len(nodes)
                    nodes.append(None)
                    references.append([key, child_index])
                    children.append((False, item, child_index))
                nodes[index] = ["dict", references]
            else:
                for item in current:
                    child_index = len(nodes)
                    nodes.append(None)
                    references.append(child_index)
                    children.append((False, item, child_index))
                nodes[index] = ["list", references]

            stack.extend(reversed(children))
        else:
            raise ValueError("unsupported value type")

    return json.dumps(nodes, ensure_ascii=True, allow_nan=False)


def _decode(encoded: str) -> Any:
    nodes = json.loads(encoded)
    values: list[Any] = [None] * len(nodes)

    for index, (kind, data) in enumerate(nodes):
        if kind == "str":
            values[index] = data
        elif kind == "bool":
            values[index] = data
        elif kind == "int":
            values[index] = int(data)
        elif kind == "float":
            values[index] = float(data)
        elif kind == "list":
            values[index] = []
        elif kind == "dict":
            values[index] = {}

    for index, (kind, data) in enumerate(nodes):
        if kind == "list":
            values[index].extend(values[reference] for reference in data)
        elif kind == "dict":
            values[index].update((key, values[reference]) for key, reference in data)

    return values[0]


class Cache:
    def __init__(
        self, namespace: str, *, clock: Callable[[], float] = time.time
    ) -> None:
        _validate_name(namespace, 128, "namespace")
        self._prefix = namespace.encode("utf-8", "surrogatepass").hex() + "."
        self._clock = clock

    def _stored_key(self, key: str) -> str:
        _validate_name(key, 512, "key")
        return self._prefix + key.encode("utf-8", "surrogatepass").hex()

    async def _remove(self, stored_key: str) -> None:
        try:
            await custom_database.delete(stored_key)
        except NotFoundException:
            pass

    async def _read(self, stored_key: str) -> Any:
        try:
            entry = await custom_database.get(stored_key)
        except NotFoundException:
            return None

        expiry = entry["expiry"]
        if expiry != "" and self._clock() >= float(expiry):
            await self._remove(stored_key)
            return None
        return entry

    async def _write(
        self, stored_key: str, kind: str, value: Any, expiry: str = ""
    ) -> None:
        encoded = _encode(value)
        await custom_database.set(
            stored_key, {"kind": kind, "data": encoded, "expiry": expiry}
        )

    @staticmethod
    def _require_kind(entry: Any, kind: str) -> None:
        if entry is not None and entry["kind"] != kind:
            raise ValueError("key holds a different kind of value")

    async def get(self, key: str) -> Any:
        stored_key = self._stored_key(key)
        entry = await self._read(stored_key)
        self._require_kind(entry, "value")
        return None if entry is None else _decode(entry["data"])

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        stored_key = self._stored_key(key)
        encoded = _encode(value)
        if ttl is not None:
            _validate_ttl(ttl)
        expiry = "" if ttl is None else str(self._clock() + ttl)
        await custom_database.set(
            stored_key, {"kind": "value", "data": encoded, "expiry": expiry}
        )

    async def delete(self, key: str) -> bool:
        stored_key = self._stored_key(key)
        entry = await self._read(stored_key)
        if entry is None:
            return False
        await self._remove(stored_key)
        return True

    async def incr(self, key: str, by: int = 1) -> int:
        stored_key = self._stored_key(key)
        if type(by) is not int:
            raise ValueError("by must be an integer")
        entry = await self._read(stored_key)
        self._require_kind(entry, "value")
        value = 0 if entry is None else _decode(entry["data"])
        if type(value) is not int:
            raise ValueError("stored value must be an integer")
        result = value + by
        await self._write(
            stored_key, "value", result, "" if entry is None else entry["expiry"]
        )
        return result

    async def expire(self, key: str, ttl: float) -> bool:
        stored_key = self._stored_key(key)
        _validate_ttl(ttl)
        entry = await self._read(stored_key)
        if entry is None:
            return False
        entry["expiry"] = str(self._clock() + ttl)
        await custom_database.set(stored_key, entry)
        return True

    async def ttl(self, key: str) -> float:
        stored_key = self._stored_key(key)
        entry = await self._read(stored_key)
        if entry is None:
            return -2.0
        if entry["expiry"] == "":
            return -1.0
        remaining = float(entry["expiry"]) - self._clock()
        if remaining <= 0:
            await self._remove(stored_key)
            return -2.0
        return float(remaining)

    async def keys(self, prefix: str = "") -> list[str]:
        if not isinstance(prefix, str):
            raise ValueError("prefix must be a string")
        encoded_prefix = prefix.encode("utf-8", "surrogatepass").hex()
        result = []
        async for stored_key in custom_database.keys(self._prefix + encoded_prefix):
            if not stored_key.startswith(self._prefix + encoded_prefix):
                continue
            key = bytes.fromhex(stored_key[len(self._prefix):]).decode(
                "utf-8", "surrogatepass"
            )
            if key.startswith(prefix) and await self._read(stored_key) is not None:
                result.append(key)
        return sorted(result)

    async def hset(self, key: str, field: str, value: Any) -> bool:
        stored_key = self._stored_key(key)
        _validate_name(field, 512, "field")
        _encode(value)
        entry = await self._read(stored_key)
        self._require_kind(entry, "hash")
        mapping = {} if entry is None else _decode(entry["data"])
        created = field not in mapping
        mapping[field] = value
        await self._write(
            stored_key, "hash", mapping, "" if entry is None else entry["expiry"]
        )
        return created

    async def hget(self, key: str, field: str) -> Any:
        stored_key = self._stored_key(key)
        _validate_name(field, 512, "field")
        entry = await self._read(stored_key)
        self._require_kind(entry, "hash")
        return None if entry is None else _decode(entry["data"]).get(field)

    async def hdel(self, key: str, *fields: str) -> int:
        stored_key = self._stored_key(key)
        if not fields:
            raise ValueError("at least one field is required")
        for field in fields:
            _validate_name(field, 512, "field")
        entry = await self._read(stored_key)
        self._require_kind(entry, "hash")
        if entry is None:
            return 0
        mapping = _decode(entry["data"])
        removed = 0
        for field in fields:
            if field in mapping:
                del mapping[field]
                removed += 1
        if removed:
            if mapping:
                await self._write(stored_key, "hash", mapping, entry["expiry"])
            else:
                await self._remove(stored_key)
        return removed

    async def hgetall(self, key: str) -> dict[str, Any]:
        stored_key = self._stored_key(key)
        entry = await self._read(stored_key)
        self._require_kind(entry, "hash")
        return {} if entry is None else _decode(entry["data"])

    async def hkeys(self, key: str) -> list[str]:
        return sorted(await self.hgetall(key))

    async def _push(self, key: str, values: tuple[Any, ...], left: bool) -> int:
        stored_key = self._stored_key(key)
        if not values:
            raise ValueError("at least one value is required")
        for value in values:
            _encode(value)
        entry = await self._read(stored_key)
        self._require_kind(entry, "list")
        items = [] if entry is None else _decode(entry["data"])
        if left:
            items[0:0] = reversed(values)
        else:
            items.extend(values)
        await self._write(
            stored_key, "list", items, "" if entry is None else entry["expiry"]
        )
        return len(items)

    async def lpush(self, key: str, *values: Any) -> int:
        return await self._push(key, values, True)

    async def rpush(self, key: str, *values: Any) -> int:
        return await self._push(key, values, False)

    async def _pop(self, key: str, left: bool) -> Any:
        stored_key = self._stored_key(key)
        entry = await self._read(stored_key)
        self._require_kind(entry, "list")
        if entry is None:
            return None
        items = _decode(entry["data"])
        value = items.pop(0 if left else -1)
        if items:
            await self._write(stored_key, "list", items, entry["expiry"])
        else:
            await self._remove(stored_key)
        return value

    async def lpop(self, key: str) -> Any:
        return await self._pop(key, True)

    async def rpop(self, key: str) -> Any:
        return await self._pop(key, False)

    async def lrange(self, key: str, start: int, stop: int) -> list[Any]:
        stored_key = self._stored_key(key)
        if type(start) is not int or type(stop) is not int:
            raise ValueError("start and stop must be integers")
        entry = await self._read(stored_key)
        self._require_kind(entry, "list")
        if entry is None:
            return []
        items = _decode(entry["data"])
        length = len(items)
        if start < 0:
            start += length
        if stop < 0:
            stop += length
        start = max(start, 0)
        stop = min(stop, length - 1)
        if start > stop or start >= length:
            return []
        return items[start:stop + 1]

    async def llen(self, key: str) -> int:
        stored_key = self._stored_key(key)
        entry = await self._read(stored_key)
        self._require_kind(entry, "list")
        return 0 if entry is None else len(_decode(entry["data"]))
