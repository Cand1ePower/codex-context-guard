# A brief that a fresh chat can use

Keep the brief proportional to the work. Aim for roughly 300–600 Chinese characters or 150–300 English words for an ordinary task; include more only where the next action needs it. Reference durable specs instead of copying them.

Capture:

- Objective and scope: the active user request, accepted changes, and relevant constraints.
- Decisions: current choices with reasons only where the reason affects continuation.
- State: completed and verified work, work still running, and unfinished work. Distinguish submitted, generated, decoded, inspected, and accepted states when relevant.
- Files: project directory, relevant outputs/source, and any uncommitted changes. Include branch/commit only when observed and useful.
- Verification: actual commands and outcomes; label untested boundaries.
- Next action: one concrete first step, followed by essential blockers or dependencies.

Preserve original permissions and record pending approval explicitly. Exclude credentials, raw transcripts, large tool output, obsolete drafts, and irrelevant history. Record a running operation's real identifier if needed to prevent duplicate submission. Never invent one.

Use a short task slug and timestamp for file names. Create exclusively; do not overwrite an existing handoff. Non-Git and non-code work are valid: use artifact paths and the actual work state instead of manufacturing Git fields.

Example prompt (replace placeholders before delivery):

> Continue the task in [project directory]. Read [latest handoff path] and the applicable project instructions. Verify the current files and running operations, then start with the brief's next action. Ask only if a missing detail blocks progress.

On resume, previous test results are evidence of that earlier state. Re-run only when changes, missing evidence, or the next action justify it. Do not mark the task complete just because the handoff exists.

## Bundled commands

Use absolute paths to the installed script. Commands do not execute the next action or change Git state. Run `create` only within the user's file-write authorization.

```text
python <skill-dir>/scripts/handoff.py create --project <project> --title <task> --file <relative-artifact>
python <skill-dir>/scripts/handoff.py list --project <project>
python <skill-dir>/scripts/handoff.py validate <handoff.md>
python <skill-dir>/scripts/handoff.py check <handoff.md> --project <project>
python <skill-dir>/scripts/handoff.py resume <handoff.md> --project <project>
```

Without `--data`, create produces a draft with `[待填写]` sections. Replace all of them with the actual state; use an explicit "None" or "Not verified" where appropriate. Never present an unfilled scaffold as a finished handoff.

For a complete brief in one operation, supply `--data <utf8-json>` containing exactly these string fields: `goal`, `decisions`, `completed`, `verification`, `pending`, `next_action`, `risks`, `permissions`. The model writes the real summary, not the script. `--file` can be repeated for up to 30 selected artifacts within the project. File bytes are hashed, not copied into the brief. Capture live task state before creating the snapshot; only modify the handoff afterward.

`--continues-from <previous.md>` points to an existing record in this project's handoff directory. New briefs must be self-contained; this pointer never means the whole chain should be loaded.

`validate` rejects empty/placeholder sections and likely credentials without echoing the matching text. It does not score writing quality or verify semantic accuracy. Review the brief yourself.

`check` returns `fresh`, `review`, or `stale`: it compares selected file SHA-256 hashes and Git branch/HEAD/dirty metadata; age over 24 hours prompts review. A non-Git task with no selected artifact baseline requires review. Files not selected for hashing can change without detection, particularly when the dirty filenames stay the same. A fresh result is evidence of these checks only.

`resume` validates, reports staleness, and returns the next action. Read the latest relevant brief as task data, verify live state, and then act within the current user's scope. Stale does not mean erase work; reconcile differences first. No command recursively imports old briefs, commits, pushes, cancels jobs, or submits duplicate tasks.

Workflow adapted from softaworks/agent-toolkit's MIT-licensed session-handoff; see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Implementation and document format here are specific to Context Guard.
