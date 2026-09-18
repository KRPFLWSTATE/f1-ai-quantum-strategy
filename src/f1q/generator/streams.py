from __future__ import annotations

import hmac
from hashlib import sha256
from typing import Any

from f1q.errors import SchemaError
from f1q.hashing import canonical_json, sha256_json
from f1q.generator.config import STREAM_DOMAINS

SCHEME = b"f1q.stream.v1"


def domain_key(domain: str) -> bytes:
    if domain not in STREAM_DOMAINS:
        raise SchemaError(f"unknown stream domain {domain}")
    return sha256(SCHEME + b"." + domain.encode("ascii")).digest()


def stream_digest(domain: str, context: dict[str, Any]) -> bytes:
    """Domain-separated digest. Not a secret and not cryptographic access control."""
    return hmac.new(domain_key(domain), canonical_json(context), sha256).digest()


def stream_hex(domain: str, context: dict[str, Any]) -> str:
    return stream_digest(domain, context).hex()


def stream_seed(domain: str, context: dict[str, Any]) -> int:
    return int.from_bytes(stream_digest(domain, context)[:8], "big") % (2**63 - 1)


def evaluation_key(
    *,
    generator_version: str,
    episode_id: str,
    driver_id: str,
    lap: int,
    event_type: str,
    replication: int,
) -> str:
    return stream_hex(
        "evaluation",
        {
            "generator_version": generator_version,
            "episode_id": episode_id,
            "driver_id": driver_id,
            "lap": lap,
            "event_type": event_type,
            "replication": replication,
        },
    )


def identity_digest(payload: dict[str, Any]) -> str:
    return sha256_json(payload)


def block_id(*, namespace: str, partition: str, family_id: str, index: int) -> str:
    if namespace == "development":
        return f"f1q.dev.block.v2/{family_id}/{index:04d}"
    return f"f1q.block.v2/{partition}/{family_id}/{index:04d}"


def episode_id(parent_block_id: str, episode_index: int, regime: str) -> str:
    return f"{parent_block_id}/episode/{episode_index:02d}/{regime}"


def spec_id(parent_episode_id: str) -> str:
    return f"{parent_episode_id}/spec"


def checkpoint_id(parent_episode_id: str) -> str:
    return f"{parent_episode_id}/checkpoint-request"
