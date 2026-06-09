---
name: multi-script-coordinated-update
description: Workflow command scaffold for multi-script-coordinated-update in algotrading.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /multi-script-coordinated-update

Use this workflow when working on **multi-script-coordinated-update** in `algotrading`.

## Goal

Makes coordinated changes across multiple trading scripts, often for logging, code cleanup, or shared logic updates.

## Common Files

- `avg_testaccount.py`
- `blshlimit.py`
- `constants.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit multiple strategy script files (e.g., avg_testaccount.py, blshlimit.py).
- Optionally update shared files (e.g., constants.py).
- Commit all changes together.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.