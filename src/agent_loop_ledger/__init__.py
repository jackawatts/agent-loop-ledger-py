"""Detect dead-end loops in agentic tool-calling workflows.

Keeps a ledger of tool calls and their outcomes and reports three
deterministic signals over a sliding window: call repeats (same tool, same
normalised arguments), result repeats (differing calls returning the
identical normalised result, so no new information is arriving) and error
runs (consecutive failures of the same class).
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

__all__ = [
    "UNSET",
    "LedgerVerdict",
    "ToolCall",
    "canonicalise",
    "classify_error",
    "fingerprint",
    "inspect_ledger",
    "result_fingerprint",
]


class _Unset:
    def __repr__(self) -> str:
        return "UNSET"


UNSET: Any = _Unset()
"""Sentinel for "not recorded", distinct from a tool genuinely returning None."""


@dataclass(frozen=True)
class ToolCall:
    tool_name: str
    args: Any = None
    output: Any = UNSET
    error: Any = UNSET


@dataclass(frozen=True)
class LedgerVerdict:
    repeats: int
    """Highest count of an identical normalised call in the window."""
    worst_offender: str | None = None
    stale_results: int = 0
    """Highest count of distinct calls in the window returning an identical (tool, output) result."""
    stale_result_tool: str | None = None
    consecutive_errors: int = 0
    """Length of the trailing run of same-class errors."""
    error_class: str | None = None


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
    # default=repr: detection must never crash the loop on unserialisable values.
    return json.dumps(value, default=repr)


def fingerprint(tool_name: str, args: Any = None) -> str:
    return f"{tool_name.lower()}({canonicalise(args)})"


def result_fingerprint(tool_name: str, output: Any) -> str:
    return f"{tool_name.lower()}=>{canonicalise(output)}"


def classify_error(error: Any) -> str:
    if isinstance(error, BaseException):
        return type(error).__name__.lower()
    if isinstance(error, str):
        return error.strip().lower()
    if isinstance(error, dict):
        label = next(
            (error[k] for k in ("code", "status", "name") if error.get(k) is not None),
            None,
        )
        if label is not None:
            return str(label).strip().lower()
    return canonicalise(error)


def inspect_ledger(calls: Sequence[ToolCall], *, window: int = 10) -> LedgerVerdict:
    recent = list(calls)[-window:] if window > 0 else []

    call_counts: dict[str, int] = {}
    result_sources: dict[str, set[str]] = {}
    result_tools: dict[str, str] = {}
    for call in recent:
        key = fingerprint(call.tool_name, call.args)
        call_counts[key] = call_counts.get(key, 0) + 1
        if call.output is not UNSET:
            result_key = result_fingerprint(call.tool_name, call.output)
            result_sources.setdefault(result_key, set()).add(key)
            result_tools.setdefault(result_key, call.tool_name)

    def max_entry(counts: dict[str, int]) -> tuple[int, str | None]:
        best_count, best_key = 0, None
        for key, count in counts.items():
            if count > best_count:
                best_count, best_key = count, key
        return best_count, best_key

    repeats, worst_offender = max_entry(call_counts)
    stale_results, stale_result_key = max_entry(
        {key: len(sources) for key, sources in result_sources.items()}
    )

    consecutive_errors = 0
    error_class: str | None = None
    for call in reversed(recent):
        if call.error is UNSET:
            break
        cls = classify_error(call.error)
        if error_class is None:
            error_class = cls
        elif cls != error_class:
            break
        consecutive_errors += 1

    return LedgerVerdict(
        repeats=repeats,
        worst_offender=worst_offender,
        stale_results=stale_results,
        stale_result_tool=(
            None if stale_result_key is None else result_tools[stale_result_key]
        ),
        consecutive_errors=consecutive_errors,
        error_class=error_class,
    )
