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
