---
name: single-script-feature-or-bugfix
description: Workflow command scaffold for single-script-feature-or-bugfix in algotrading.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /single-script-feature-or-bugfix

Use this workflow when working on **single-script-feature-or-bugfix** in `algotrading`.

## Goal

Implements a new feature or fixes a bug in a single trading strategy script (e.g., blshlimit.py or avg_testaccount.py).

## Common Files

- `blshlimit.py`
- `avg_testaccount.py`
- `avgdowndouble-quotes.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit the relevant strategy script file (e.g., blshlimit.py or avg_testaccount.py).
- Commit the changes with a descriptive message.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.