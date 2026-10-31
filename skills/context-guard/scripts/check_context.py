#!/usr/bin/env python3
"""Read bounded, local Codex telemetry. Never emit conversation content."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

MAX_READ_BYTES = 4 * 1024 * 1024


def utc_time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def unknown(reason):
    return {"status": "unknown", "reason": reason, "should_notify": False}


def locate_session(codex_home, session_id):
    # No most-recent-file heuristic: another chat may be doing unrelated work.
    if not session_id or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", session_id):
        return None, "missing_or_invalid_session_id"
    matches = list((codex_home / "sessions").glob(f"**/*-{session_id}.jsonl"))
    if len(matches) != 1:
        return None, "session_not_found" if not matches else "ambiguous_session"
    return matches[0], None


def read_sample(path):
    """Only parse a bounded tail; ignore an in-progress trailing JSON line."""
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        start = max(0, size - MAX_READ_BYTES)
        stream.seek(start)
        lines = stream.read(MAX_READ_BYTES).splitlines()
    if start:
        lines = lines[1:]  # The first line may be incomplete.
    compacted_after = False
    sample = None
    for line in reversed(lines):
        if b'"token_count"' not in line and b'"compacted"' not in line:
            continue
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "compacted":
            if sample is None:
                compacted_after = True
            else:
                return (*sample, compacted_after, event.get("timestamp"))
        payload = event.get("payload")
        if (event.get("type") == "event_msg" and isinstance(payload, dict)
                and payload.get("type") == "token_count"):
            info = payload.get("info")
            if info is None:
                continue
            if sample is None:
                sample = (event.get("timestamp"), info)
    return (*(sample or (None, None)), compacted_after, None)


def evaluate(path, now=None, max_age=600, warn=50, urgent=70, state=None):
    timestamp, info, compacted_after, compaction_timestamp = read_sample(path)
    if info is None:
        return unknown("no_recent_token_sample_in_bounded_tail")
    if not isinstance(info, dict):
        return unknown("unsupported_telemetry_schema")
    usage = info.get("last_token_usage")
    window = info.get("model_context_window")
    if not isinstance(usage, dict):
        return unknown("missing_last_request_usage")
    input_tokens = usage.get("input_tokens")
    if not positive_int(input_tokens) or not positive_int(window) or input_tokens > window:
        return unknown("invalid_input_or_window")
    sampled_at = utc_time(timestamp)
    if sampled_at is None:
        return unknown("missing_or_invalid_timestamp")
    now = now or datetime.now(timezone.utc)
    age = (now - sampled_at).total_seconds()
    if age < -60:
        return unknown("sample_timestamp_in_future")
    percent = 100 * input_tokens / window
    level = "high" if percent >= urgent else "watch" if percent >= warn else "normal"
    result = {
        "status": "ok", "source": "local_codex_last_request",
        "sampled_at": timestamp, "age_seconds": round(max(0, age)),
        "last_input_tokens": input_tokens, "reported_context_window": window,
        "last_input_percent": round(percent, 1), "level": level,
        "should_notify": False,
    }
    if compacted_after or age > max_age:
        result.update(status="stale", reason="compaction_after_sample" if compacted_after
                      else "sample_too_old")
        return result
    state = state if isinstance(state, dict) else {}
    rank = {"normal": 0, "watch": 1, "high": 2}
    old_input = state.get("input_tokens")
    reset = positive_int(old_input) and input_tokens < old_input * 0.65
    previous_sample = utc_time(state.get("sampled_at"))
    compaction_time = utc_time(compaction_timestamp)
    reset = reset or (compaction_time is not None and previous_sample is not None
                      and compaction_time > previous_sample)
    reset = reset or (state.get("window") is not None and state["window"] != window)
    old_level = state.get("level")
    old_rank = 0 if reset or not isinstance(old_level, str) else rank.get(old_level, 0)
    result["should_notify"] = rank[level] > old_rank
    return result


def read_state(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record_state(path, result):
    if result["status"] != "ok" or not result.get("should_notify"):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"level": result["level"], "input_tokens": result["last_input_tokens"],
             "window": result["reported_context_window"],
             "sampled_at": result["sampled_at"]}
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".context-guard-", delete=False) as stream:
            temp_name = stream.name
            json.dump(value, stream)
        os.replace(temp_name, path)
    finally:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-file", type=Path, help="Explicit session JSONL; no auto-selection")
    parser.add_argument("--codex-home", type=Path,
                        default=Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"))
    parser.add_argument("--session-id", default=os.environ.get("CODEX_THREAD_ID")
                        or os.environ.get("CODEX_SESSION_ID"))
    parser.add_argument("--state-dir", type=Path, help="Default: CODEX_HOME/context-guard")
    parser.add_argument("--warn-percent", type=float, default=50)
    parser.add_argument("--urgent-percent", type=float, default=70)
    parser.add_argument("--max-age-seconds", type=int, default=600)
    parser.add_argument("--record", action="store_true", help="Acknowledge a reminder actually shown")
    args = parser.parse_args(argv)
    if not 0 < args.warn_percent < args.urgent_percent <= 100 or args.max_age_seconds <= 0:
        parser.error("require 0 < warn < urgent <= 100 and positive max age")
    try:
        path, error = ((args.session_file, None) if args.session_file else
                       locate_session(args.codex_home, args.session_id))
        if error:
            result = unknown(error)
        else:
            path = path.resolve()
            key = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:24]
            state_path = (args.state_dir or args.codex_home / "context-guard") / f"{key}.json"
            result = evaluate(path, max_age=args.max_age_seconds, warn=args.warn_percent,
                              urgent=args.urgent_percent, state=read_state(state_path))
            if args.record:
                record_state(state_path, result)
    except OSError:
        result = unknown("telemetry_or_state_unavailable")
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
