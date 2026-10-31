---
name: context-guard
description: Check Codex context telemetry, suggest a fresh chat at task boundaries, and create concise handoffs when context grows or work changes direction.
---

# Context Guard

Keep long work restartable without interrupting unfinished operations. This skill provides turn-time checks, not a background alarm or automatic chat switching.

## Check

At the start of substantive work, after unusually large tool output, or at a major task boundary, run the bundled script using its absolute installed path:

```text
python <skill-dir>/scripts/check_context.py
```

It uses `CODEX_THREAD_ID` (or `CODEX_SESSION_ID`) to locate only this session under `$CODEX_HOME/sessions` / `~/.codex/sessions`. It emits small JSON, never the transcript. Do not read entire logs or choose the newest session across unrelated chats. If local telemetry is unavailable, use task-boundary judgment and say usage is unknown; do not invent a percentage.

`last_input_percent` is the last reported request's input tokens divided by its reported context window, rounded. It is a proxy, not a live meter, quality score, bill, or cumulative session total. Cached tokens still occupy context. Stale or malformed telemetry must not trigger a numeric alarm.

Default policy (configurable CLI percentages; these are workflow preferences, not model limits):

- Below 50%: normally continue without mentioning the check.
- At 50%: if `should_notify`, briefly recommend wrapping the current phase and preparing a handoff.
- At 70%: if `should_notify`, recommend a fresh chat after the next safe stopping point and prepare the handoff for substantial unfinished work.
- A separate project or independent major objective is a fresh-chat boundary even below those percentages. A small related follow-up is not.
- Repeated loss of accepted requirements or a large backlog of superseded attempts can justify an earlier suggestion; identify the observed reason, not an invented usage figure.

Finish the current safe unit first. Never cancel a render, deployment, download, edit, or ongoing task merely to switch chats. If the user chooses to continue, keep working. A warning is advisory, not a permission gate.

After actually giving a numeric reminder, run the same check with `--record` to suppress repeats at that level. Re-check before recording; if usage changed, use the returned result. State is local, session-specific metadata. Compaction or a large input drop permits a new reminder. Do not acknowledge reminders silently without telling the user.

## Handoff and resume

When a new chat would help, read [references/handoff.md](references/handoff.md). Produce a self-contained brief with the objective, decisions, verified state, files, unresolved work, and the next action. Prefer the brief in chat; for substantial work, save one UTF-8 file under the project's `.codex/handoffs/` if file creation is authorized. Link the file and give a paste-ready new-chat prompt.

Read only the latest relevant brief when resuming, then verify live files and repository state. Use older records only for a specific missing detail. Do not re-import the whole conversation or every prior handoff. Do not treat a brief as authorization for new external actions.

The script requires Python 3.10+ and uses the standard library only. A short global AGENTS.md routing rule is needed for regular checks; skill discovery alone does not guarantee checks on every turn. Local JSONL telemetry is an implementation detail and can change. Without it, the qualitative handoff workflow still works.
