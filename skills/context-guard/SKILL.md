---
name: context-guard
description: Monitor Codex context window and token usage, suggest new chats for context rot, and create, validate, check or resume session handoffs.
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

Default policy (workflow preferences, not measured quality limits): the watch level is reached at 35% OR 128,000 input tokens; the high level at 50% OR 192,000 input tokens. Either condition suffices. Budgets use decimal tokens and can be disabled with `--warn-tokens 0 --urgent-tokens 0`. For evidence and limitations, read [references/context-quality.md](references/context-quality.md) only when explaining or calibrating thresholds.

- At the normal level: continue without mentioning the check.
- At the watch level: if `should_notify`, briefly recommend wrapping the current phase and preparing a handoff.
- At the high level: if `should_notify`, recommend a fresh chat after the next safe stopping point and prepare the handoff for substantial unfinished work.
- A separate project or independent major objective is a fresh-chat boundary even below those percentages. A small related follow-up is not.
- Repeated loss of accepted requirements or a large backlog of superseded attempts can justify an earlier suggestion; identify the observed reason, not an invented usage figure.
- If a fresh chat already exceeds the budgets because of fixed instructions or required source material, suggest reducing that fixed payload or configuring task-specific budgets. Do not send the user into repeated restarts that cannot remove it.

Finish the current safe unit first. Never cancel a render, deployment, download, edit, or ongoing task merely to switch chats. If the user chooses to continue, keep working. A warning is advisory, not a permission gate.

After actually giving a numeric reminder, run the same check with `--record` to suppress repeats at that level. Re-check before recording; if usage changed, use the returned result. State is local, session-specific metadata. Compaction or a large input drop permits a new reminder. Do not acknowledge reminders silently without telling the user.

## Handoff and resume

When a new chat would help, or the user asks to save/resume state, read [references/handoff.md](references/handoff.md). The bundled `scripts/handoff.py` provides `create`, `list`, `validate`, `check`, and `resume`. Use it for substantial file-based handoffs; a small task can use a brief directly in chat. It supports non-Git work, selected artifact hashes, Git metadata, lineage pointers, and secret/placeholder checks. Validation is structural, not proof of truth or secret-free content. Save UTF-8 files under the project's `.codex/handoffs/` only when creation is authorized. Link the file and give a paste-ready new-chat prompt.

Read only the latest relevant brief when resuming, then verify live files and repository state. Use older records only for a specific missing detail. Do not re-import the whole conversation or every prior handoff. Do not treat a brief as authorization for new external actions.

The script requires Python 3.10+ and uses the standard library only. A short global AGENTS.md routing rule is needed for regular checks; skill discovery alone does not guarantee checks on every turn. Local JSONL telemetry is an implementation detail and can change. Without it, the qualitative handoff workflow still works.
