"""Detect dead-end loops in agentic tool-calling workflows.

Fingerprints tool calls in a normalised form (case, whitespace, key order and
empty parameters ignored) and counts repeats over a sliding window, so an
agent retrying the same call with cosmetic variations is detected.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

__all__ = ["LedgerVerdict", "canonicalise", "fingerprint", "inspect_ledger"]


@dataclass(frozen=True)
class LedgerVerdict:
    repeats: int
    worst_offender: str | None = None


def canonicalise(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value.strip().lower())
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonicalise(v) for v in value) + "]"
    if isinstance(value, dict):
        items = sorted(
            (str(k).lower(), v) for k, v in value.items() if v is not None and v != ""
        )
        return "{" + ",".join(f"{k}:{canonicalise(v)}" for k, v in items) + "}"
    return json.dumps(value)


def fingerprint(tool_name: str, args: Any = None) -> str:
    return f"{tool_name.lower()}({canonicalise(args)})"


def inspect_ledger(
    calls: Sequence[tuple[str, Any]], *, window: int = 10
) -> LedgerVerdict:
    counts: dict[str, int] = {}
    for tool_name, args in list(calls)[-window:]:
        key = fingerprint(tool_name, args)
        counts[key] = counts.get(key, 0) + 1
    repeats = 0
    worst_offender: str | None = None
    for key, count in counts.items():
        if count > repeats:
            repeats = count
            worst_offender = key
    return LedgerVerdict(repeats=repeats, worst_offender=worst_offender)
