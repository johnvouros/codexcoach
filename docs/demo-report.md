# Codex Coach Demo Report

| Generated | Window | Mode |
|---|---:|---|
| `2026-05-24 09:00` | `7d` | `beginner` |

## At A Glance

| Habit | Signal | What It Means |
|---|---:|---|
| Prompt clarity | `6.2/10` | Prompts usually have the task, but often miss the success state. |
| Verification | `18%` | Codex is checking work sometimes, but not enough for risky changes. |
| Compactions | `12` | Long runs need better checkpoints before context gets compressed. |
| Effort mix | `xhigh-heavy` | Routine work is probably using more intelligence than it needs. |

## TL;DR

1. Use medium intelligence for routine scans, reports, small edits, and formatting.
2. Add the success state to short prompts, especially when saying "continue" or "run again."
3. Keep a short project note so Codex can resume from the current facts instead of rereading long history.

## What To Change

### 1. Right-size routine work

- Why: routine tasks do not usually need the highest intelligence level.
- Where: Codex model/intelligence picker, not `AGENTS.md`.
- Do: start routine reports and small deterministic edits on medium.

### 2. Make short prompts clearer

- Why: vague prompts cause extra clarification, broader searches, or wrong assumptions.
- Where: your next prompt.
- Do: include action, target, and success state.

Example:

```text
Update the README quick start so a beginner can install, run Codex Coach, and open the generated report. Success means the README has a 3-step flow and tests still pass.
```

### 3. Add a compact project note

- Why: repeated context costs time and tokens.
- Where: project `AGENTS.md` if it applies only to one repo, or custom instructions if it is a global habit.
- Do: keep 5 to 10 lines covering purpose, entry points, verify commands, and current constraints.

Example:

```text
Before re-reading a large repo or long history, check existing summaries, reports, AGENTS.md, and recent task notes first. Use those compact notes to choose the smallest useful next file or command.
```

## Weekly Check-In

Paste this into Codex if you want a weekly review:

```text
Set a weekly Codex Coach check-in every 7 days. Use medium intelligence for the routine review. Each week, run `codex-coach report --since 7d`, read `~/.codex-coach/reports/latest.md`, compare it with the previous report, and give me a concise TL;DR with the top 3 changes and exact next actions. Escalate to high only if the report shows security risk, production risk, repeated failures, or major architecture concerns.
```

