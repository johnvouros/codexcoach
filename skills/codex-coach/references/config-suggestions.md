# Config Suggestion Policy

Codex Coach can suggest changes to global custom instructions, user-level skills, or project `AGENTS.md` files. Suggestions must be reviewable and reversible.

Recommended suggestion format:

- Evidence: one metric or repeated pattern from the report.
- Confidence: low, medium, or high.
- Change: the exact instruction text to add.
- Benefit: what should improve.
- Rollback: how to remove it if it does not help.

Common suggestions:

```md
When a task is simple, local, or status-oriented, default to medium reasoning. Reserve high or xhigh for ambiguous debugging, architecture, security, broad refactors, or unclear failures.
```

```md
Before saying a fix is complete, run the smallest meaningful verification command or inspect the live/runtime state when applicable.
```

```md
For long tasks, keep a short durable checklist or artifact ledger so work can resume safely after compaction or interruption.
```

```md
For multi-project work, prefer short project capsules over one large global instruction.
```

For repeated workflows, prefer a user skill over a long global instruction:

```md
When this workflow appears, gather [project context], follow [steps], verify with [commands], and resume from [ledger/checklist] after interruption.
```

Instruction Playbook Audit checks:

- Stale mode locks: standing rules such as "research only" or "do not implement" that may belong to a temporary task mode.
- Scope leaks: stack, UI style, or command rules in global custom instructions that should live in a project `AGENTS.md`.
- Missing verification cues: active projects with implementation-heavy usage but no test/build/lint/verify guidance.
- Missing playbooks: active project directories with no discovered nearby `AGENTS.md`.
- Safety issues: secret-shaped values or credentials in instruction files.

Suggested edits should be small, reversible, and phrased as snippets for the user to review.
