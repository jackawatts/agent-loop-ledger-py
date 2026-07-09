# agent-loop-ledger (Python)

Detect dead-end loops in agentic tool-calling workflows.

An agent that stops making progress does not always repeat itself verbatim. This library keeps a ledger of tool calls and their outcomes and reports three deterministic signals over a sliding window:

- **Call repeats**: the same tool called with the same normalised arguments. Catches retry loops, including cosmetic variations (casing, whitespace, key order, empty parameters).
- **Result repeats**: a tool returning the identical normalised result to differing calls. Catches thrashing, where the agent varies its arguments but no new information enters the context (query after query returning `[]`).
- **Error runs**: consecutive failures of the same class (same exception type, code or HTTP status). Catches an agent hammering a broken call path even when every call looks different.

Dependency free and framework agnostic: feed it `ToolCall` records from whatever agent loop you run. A TypeScript port with a Vercel AI SDK adapter lives at [agent-loop-ledger](https://github.com/jackawatts/agent-loop-ledger).

## Install

```bash
uv add git+https://github.com/jackawatts/agent-loop-ledger-py
```

## Use

```python
from agent_loop_ledger import ToolCall, inspect_ledger

verdict = inspect_ledger(
    [
        ToolCall("runSql", {"query": "select name from contacts"}, output=[]),
        ToolCall("runSql", {"query": "select middle_name from contacts"}, output=[]),
        ToolCall("runSql", {"query": "select * from custom_fields"}, output=[]),
    ]
)
verdict.repeats        # 1: every call was different...
verdict.stale_results  # 3: ...but nothing new came back three times
verdict.consecutive_errors  # 0
```

In an agent loop, collect the calls made so far (with outputs and errors where you have them) and act on the verdict: warn the model in its instructions when a signal reaches 2, stop the loop at 3. `output` and `error` default to the `UNSET` sentinel, so a tool that genuinely returned `None` still counts as a recorded result.

Normalisation rules: tool names and string values are lowercased and stripped, dict keys are sorted, and parameters that are `None` or `""` are dropped. Error classes are derived from the exception type name, a dict's `code`, `status` or `name`, or the normalised value itself.

Tune per use case: 3 repeats is a sensible default threshold (2 if tools are expensive or have side effects), and the window (default 10) bounds how far back signals are counted so a legitimate re-read much later in a long run is not punished.

Detection is the safety net, not the fix. If an agent loops, the tool results usually gave it nothing to act on (empty lists, bare errors). Make tool results say what to try next. And when a signal trips, log the run: every tripped ledger is a regression case for your evals.

## Develop

```bash
uv sync
uv run pytest
uv run ruff check
```
