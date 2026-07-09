# agent-loop-ledger (Python)

Detect dead-end loops in agentic tool-calling workflows.

An agent that stops making progress usually shows the same symptom: it calls the same tool with the same arguments again and again, often with cosmetic variations (different casing, extra whitespace, reordered or empty parameters). This library fingerprints every tool call in a normalised form, counts repeats over a sliding window, and tells you when the agent is stuck.

Dependency free and framework agnostic: feed it `(tool_name, args)` pairs from whatever agent loop you run. A TypeScript port with a Vercel AI SDK adapter lives at [agent-loop-ledger](https://github.com/jackawatts/agent-loop-ledger).

## Install

```bash
uv add git+https://github.com/jackawatts/agent-loop-ledger-py
```

## Use

```python
from agent_loop_ledger import inspect_ledger

verdict = inspect_ledger(
    [
        ("runSql", {"query": "SELECT 1"}),
        ("RunSQL", {"query": " select 1 "}),
    ]
)
# LedgerVerdict(repeats=2, worst_offender='runsql({query:"select 1"})')
```

In an agent loop, collect the tool calls made so far and act on the verdict: warn the model in its instructions on the second repeat, stop the loop on the third. For example, with the OpenAI Agents SDK, check the ledger in a tool-call hook and raise or inject guidance; with a hand-rolled loop, check it before executing each batch of tool calls.

Normalisation rules: tool names and string values are lowercased and stripped, dict keys are sorted, and parameters that are `None` or `""` are dropped. Two calls that differ only in those ways count as the same call.

Tune per use case: 3 repeats is a sensible default threshold (2 if tools are expensive or have side effects), and the window (default 10) bounds how far back repeats are counted so a legitimate re-read much later in a long run is not punished.

Detection is the safety net, not the fix. If an agent loops, the tool results usually gave it nothing to act on (empty lists, bare errors). Make tool results say what to try next.

## Develop

```bash
uv sync
uv run pytest
uv run ruff check
```
