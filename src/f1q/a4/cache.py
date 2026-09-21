"""Byte-bounded scientific caches. Evict by bytes, not merely entry count."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


def _nbytes(obj: Any) -> int:
    if obj is None:
        return 0
    if hasattr(obj, "nbytes"):
        return int(obj.nbytes)
    if isinstance(obj, (bytes, bytearray, memoryview)):
        return len(obj)
    if isinstance(obj, str):
        return len(obj.encode("utf-8"))
    if isinstance(obj, dict):
        return sum(_nbytes(k) + _nbytes(v) for k, v in obj.items()) + 64
    if isinstance(obj, (list, tuple)):
        return sum(_nbytes(x) for x in obj) + 64
    if isinstance(obj, (int, float, bool)):
        return 24
    return 128


class ByteBoundedCache:
    """LRU cache with a hard byte ceiling. Records hits, misses, evictions, max bytes."""

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = int(max_bytes)
        self._data: OrderedDict[str, Any] = OrderedDict()
        self._sizes: dict[str, int] = {}
        self.bytes = 0
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.max_bytes_observed = 0

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._data:
            self.hits += 1
            self._data.move_to_end(key)
            rec = self._data[key]
            if isinstance(rec, dict):
                out = dict(rec)
                out["cache_hit"] = True
                return out
            return rec
        self.misses += 1
        return default

    def __getitem__(self, key: str) -> Any:
        rec = self.get(key)
        if rec is None and key not in self._data:
            raise KeyError(key)
        return rec

    def put(self, key: str, value: Any) -> None:
        size = max(1, _nbytes(value))
        if key in self._data:
            self.bytes -= self._sizes[key]
        while self._data and (self.bytes + size) > self.max_bytes:
            old_k, _ = self._data.popitem(last=False)
            self.bytes -= self._sizes.pop(old_k, 0)
            self.evictions += 1
        if size > self.max_bytes:
            # Single object larger than the ceiling: do not retain.
            self.evictions += 1
            self._data.pop(key, None)
            self._sizes.pop(key, None)
            return
        self._data[key] = value
        self._data.move_to_end(key)
        self._sizes[key] = size
        self.bytes += size
        if self.bytes > self.max_bytes_observed:
            self.max_bytes_observed = self.bytes

    def __setitem__(self, key: str, value: Any) -> None:
        self.put(key, value)

    def clear_prefix(self, prefix: str) -> int:
        keys = [k for k in self._data if k.startswith(prefix)]
        for k in keys:
            self.bytes -= self._sizes.pop(k, 0)
            del self._data[k]
        return len(keys)

    def stats(self) -> dict[str, int]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "entries": len(self._data),
            "bytes": self.bytes,
            "max_bytes": self.max_bytes,
            "max_bytes_observed": self.max_bytes_observed,
        }
