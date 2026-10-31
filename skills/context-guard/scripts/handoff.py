#!/usr/bin/env python3
"""Create, list, validate, check, and resume compact local session handoffs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

FIELDS = {
    "goal": "Goal and scope", "decisions": "Accepted decisions",
    "completed": "Completed and verified", "verification": "Verification evidence",
    "pending": "Pending work and running operations", "next_action": "Next action",
    "risks": "Open questions and risks", "permissions": "Authorization boundaries",
}
META = re.compile(r"<!-- context-guard:metadata (\{[^\n]*\}) -->")
MAX_DOCUMENT = 128 * 1024
SECRET_PATTERNS = [r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----",
                   r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
                   r"\bsk-[A-Za-z0-9_-]{20,}\b", r"https?://[^\s/:]+:[^\s/@]+@",
                   r"(?im)^\s*(?:api[_-]?key|password|access[_-]?token)\s*[:=]\s*['\"]?[^\s'\"]{8,}"]


def git(project, *args):
    try:
        result = subprocess.run(["git", "--no-optional-locks", "-c", "core.quotepath=false", *args],
                                cwd=project, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=10)
        return result.stdout.rstrip("\r\n") if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def snapshot(project):
    root = git(project, "rev-parse", "--show-toplevel")
    if root is None:
        return {"git": False}
    raw = git(project, "status", "--porcelain=v1", "--untracked-files=all")
    relative = (project / ".codex/handoffs").relative_to(Path(root).resolve()).as_posix() + "/"
    # Exclude the handoff's own artifacts from dirty-state comparisons.
    rows = [line for line in (raw or "").splitlines() if not line[3:].startswith(relative)]
    return {"git": True, "head": git(project, "rev-parse", "HEAD"),
            "branch": git(project, "branch", "--show-current"), "dirty": rows[:100],
            "status_complete": raw is not None and len(rows) <= 100}


def file_fingerprint(project, value):
    path = (project / value).resolve()
    try:
        relative = path.relative_to(project)
    except ValueError:
        raise ValueError("Referenced files must stay inside the project") from None
    if not path.is_file():
        raise ValueError("A referenced file is missing or is not a file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": relative.as_posix(), "sha256": digest.hexdigest()}


def secret_lines(text):
    return sorted({text[:match.start()].count("\n") + 1 for pattern in SECRET_PATTERNS
                   for match in re.finditer(pattern, text)})


def parse(text):
    match = META.search(text)
    if not match:
        raise ValueError("Missing Context Guard metadata")
    try:
        meta = json.loads(match[1])
    except ValueError:
        raise ValueError("Invalid metadata JSON") from None
    if (not isinstance(meta, dict) or meta.get("version") != 1
            or not isinstance(meta.get("project"), str)
            or not isinstance(meta.get("snapshot"), dict)
            or not isinstance(meta.get("files"), list)):
        raise ValueError("Unsupported metadata schema")
    bodies = {}
    for key, heading in FIELDS.items():
        section = re.search(r"(?ms)^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", text)
        bodies[key] = section[1].strip() if section else ""
    return meta, bodies


def validate_text(text):
    errors = []
    try:
        _, fields = parse(text)
        for key, body in fields.items():
            if not body or re.search(r"\[TODO[^\]]*\]|\[待填写\]", body, re.I):
                errors.append("incomplete_section:" + key)
    except ValueError as error:
        errors.append(str(error))
    lines = secret_lines(text)
    if lines:
        errors.append("possible_secret_at_lines:" + ",".join(map(str, lines)))
    return {"valid": not errors, "errors": errors,
            "scope": "structure_and_secret_heuristics_only"}


def read_document(path):
    if path.stat().st_size > MAX_DOCUMENT:
        raise ValueError("Handoff exceeds the 128 KiB document limit")
    return path.read_text(encoding="utf-8-sig")


def create(project, title, data=None, files=(), previous=None):
    project = project.resolve()
    if not project.is_dir():
        raise ValueError("Project directory does not exist")
    directory = project / ".codex/handoffs"
    # Resolve before creating anything; symlinks must not redirect writes outside the project.
    if not directory.resolve().is_relative_to(project):
        raise ValueError("Handoff directory must stay inside the project")
    if len(files) > 30:
        raise ValueError("Select at most 30 files relevant to resuming")
    if data is not None and (not isinstance(data, dict) or set(data) != set(FIELDS)
                             or any(not isinstance(v, str) for v in data.values())):
        raise ValueError("Data must contain exactly the documented string fields")
    if previous:
        previous = Path(previous).resolve()
        if not previous.is_file() or not previous.is_relative_to(directory.resolve()):
            raise ValueError("Previous handoff must exist in this project's handoff directory")
    now = datetime.now(timezone.utc)
    meta = {"version": 1, "title": title, "created_at": now.isoformat(),
            "project": str(project), "snapshot": snapshot(project),
            "files": [file_fingerprint(project, f) for f in files],
            "continues_from": previous.name if previous else None}
    title = re.sub(r"[\r\n]+", " ", title).strip()
    content = "# Handoff: " + title + "\n\n<!-- context-guard:metadata " + json.dumps(meta, ensure_ascii=True) + " -->\n\n"
    content += "Project: `" + str(project) + "`\n\n"
    if previous:
        content += "Previous record (read only if needed): " + previous.name + "\n\n"
    for key, heading in FIELDS.items():
        content += "## " + heading + "\n\n" + (data[key].strip() if data else "[待填写]") + "\n\n"
    content = content.rstrip() + "\n"
    if len(content.encode("utf-8")) > MAX_DOCUMENT:
        raise ValueError("Handoff exceeds the 128 KiB document limit")
    validation = validate_text(content)
    if secret_lines(content) or (data is not None and not validation["valid"]):
        raise ValueError("Handoff rejected: incomplete sections or possible credentials; no file written")
    slug = re.sub(r"[^\w-]+", "-", title.lower(), flags=re.UNICODE).strip("-")[:48] or "handoff"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (now.strftime("%Y%m%dT%H%M%SZ") + "-" + slug + "-" + uuid.uuid4().hex[:6] + ".md")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    return {"path": str(path), "draft": data is None, "validation": validation}


def check(path, project=None, now=None):
    meta, _ = parse(read_document(path))
    project = (project or Path(meta["project"])).resolve()
    if str(project) != str(Path(meta["project"]).resolve()):
        return {"status": "stale", "reasons": ["project_mismatch"]}
    if not project.is_dir():
        return {"status": "stale", "reasons": ["project_missing"]}
    reasons, cautions = [], []
    try:
        created = datetime.fromisoformat(meta["created_at"])
        if created.tzinfo is None:
            raise ValueError()
        hours = ((now or datetime.now(timezone.utc)) - created).total_seconds() / 3600
        if hours < -1 or hours >= 24:
            cautions.append("age_requires_review")
    except (KeyError, ValueError, TypeError):
        cautions.append("unknown_creation_time")
    live = snapshot(project)
    saved = meta["snapshot"]
    if saved.get("git") != live.get("git"):
        reasons.append("repository_state_changed")
    if saved.get("git") and live.get("git"):
        for key in ["head", "branch", "dirty"]:
            if saved.get(key) != live.get(key):
                reasons.append("git_" + key + "_changed")
        if not saved.get("status_complete") or not live.get("status_complete"):
            cautions.append("incomplete_git_status")
    for ref in meta["files"]:
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
            cautions.append("invalid_file_reference")
            continue
        try:
            current = file_fingerprint(project, ref["path"])
            if current != ref:
                reasons.append("referenced_file_changed:" + ref["path"])
        except (ValueError, OSError):
            reasons.append("referenced_file_unavailable:" + ref["path"])
    if not saved.get("git") and not meta["files"]:
        cautions.append("no_artifact_baseline")
    return {"status": "stale" if reasons else "review" if cautions else "fresh",
            "reasons": reasons + cautions,
            "scope": "selected_artifacts_and_git_metadata_only"}


def list_handoffs(project, limit=20):
    directory = project.resolve() / ".codex/handoffs"
    rows = []
    for path in sorted(directory.glob("*.md"), reverse=True)[:limit]:
        try:
            meta, _ = parse(read_document(path))
            rows.append({"path": str(path), "title": meta.get("title"), "created_at": meta.get("created_at")})
        except (ValueError, OSError):
            rows.append({"path": str(path), "status": "unreadable_or_unsupported"})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    creator = sub.add_parser("create")
    creator.add_argument("--project", type=Path, default=Path.cwd())
    creator.add_argument("--title", required=True)
    creator.add_argument("--data", type=Path, help="UTF-8 JSON with all documented string fields")
    creator.add_argument("--file", action="append", default=[], help="Selected project artifact to fingerprint")
    creator.add_argument("--continues-from", type=Path)
    listing = sub.add_parser("list")
    listing.add_argument("--project", type=Path, default=Path.cwd())
    for name in ["validate", "check", "resume"]:
        command = sub.add_parser(name)
        command.add_argument("file", type=Path)
        command.add_argument("--project", type=Path)
    args = parser.parse_args(argv)
    code = 0
    try:
        if args.command == "create":
            data = json.loads(args.data.read_text(encoding="utf-8-sig")) if args.data else None
            result = create(args.project, args.title, data, args.file, args.continues_from)
        elif args.command == "list":
            result = {"handoffs": list_handoffs(args.project)}
        elif args.command == "check":
            result = check(args.file, args.project)
        else:
            text = read_document(args.file)
            result = validate_text(text)
            code = 0 if result["valid"] else 1
            if args.command == "resume" and result["valid"]:
                _, fields = parse(text)
                result = {"validation": result, "staleness": check(args.file, args.project),
                          "next_action": fields["next_action"], "path": str(args.file.resolve()),
                          "instruction": "Read this latest brief, verify live state, and preserve authorization boundaries."}
    except (OSError, ValueError) as error:
        result, code = {"error": type(error).__name__, "message": "Operation failed; check paths, metadata, and input schema. No secret content is echoed."}, 1
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    sys.exit(main())
