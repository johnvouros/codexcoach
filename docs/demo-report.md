# Codex Coach Demo Report

This is an anonymized example based on a real Codex Coach report. Project names, hashes, and sensitive details have been replaced.

| Generated | Window | Mode |
|---|---|---|
| `2026-05-24T10:47:03+00:00` | `7d` | `expert` |

## Since Last Report

Previous report detected, but it is too recent to compare meaningfully. Codex Coach waits for a baseline at least 7 days old before showing trend results.

Most recent baseline: generated `2026-05-24T10:05:23+00:00` for window `7d`.

## At A Glance

| Metric | Value |
|---|---:|
| Sessions | 46 |
| Turns | 1,166 |
| User messages | 1,353 |
| Tool calls | 18,667 |
| Verification rate | 15.6% |
| Errors detected | 4,847 |
| Compactions | 151 |
| Prompt clarity | 5.79/10 |

## TL;DR

Start here. These are optional coaching suggestions, not errors.

### 1. Right-size reasoning effort

- Why: High reasoning dominates recent turns. To actually reduce effort, choose medium in the Codex UI or CLI for routine work. A custom instruction can only remind Codex of the preference; it cannot override a manually selected model or effort setting.
- Where: Codex UI model/effort picker or CLI model/effort flag. Optional reminder text can go in Global custom instructions.
- Scope: Actual setting change, not just a prompt.
- Do: For routine work, start the session with mini or medium in the UI/CLI.
- What to paste:

<details>
<summary>Show snippet</summary>

```md
For model effort, prefer medium for routine status checks, targeted searches, formatting, small edits, and deterministic reports. Use high or xhigh only for ambiguous debugging, architecture decisions, security review, broad refactors, or production-risk changes.
```

</details>

### 2. Checkpoint long runs

- Why: Compactions appeared in the window. For long tasks, ask Codex to keep a small task ledger and validate durable files before resuming.
- Where: Codex settings -> Custom instructions, or the project `AGENTS.md` file.
- Scope: Use settings if you want this everywhere. Use `AGENTS.md` if it should apply only to one repo.
- Do: If unsure, put it in `AGENTS.md` first so the habit stays scoped to one project.
- What to paste:

<details>
<summary>Show snippet</summary>

```md
For long tasks, keep a short task ledger with completed, in-progress, and pending steps. After compaction or interruption, verify the current file state and last successful command before continuing.
```

</details>

### 3. Tighten ambiguous prompts

- Why: A noticeable share of prompts are too short to identify the target. Include action, file/project, symptom, and success state when context is not obvious.
- Where: Codex settings -> Custom instructions.
- Scope: Settings, not the chat prompt. Use this for habits you want Codex to follow everywhere.
- Do: Open Codex settings, edit Custom instructions, paste the block below, then remove it later if it does not help.
- What to paste:

<details>
<summary>Show snippet</summary>

```md
When my prompt is vague, infer the likely task from the current repo and recent context. If the target or success state is still unclear, ask one concise question before making broad changes.
```

</details>

### 4. Use project capsules

- Why: Recent work spans several projects. Keep a short per-project `AGENTS.md` or context note so Codex does not rebuild project intent every time.
- Where: In each active project folder, open or create a file named `AGENTS.md`.
- Scope: Project file. This affects only that project, not every Codex chat.
- Do: Paste the block into `AGENTS.md` for projects where this advice actually applies.
- What to paste:

<details>
<summary>Show snippet</summary>

```md
## Project Capsule
- Purpose: <what this repo is for>
- Stack: <main frameworks, runtime, package manager>
- Entry points: <key files or commands>
- Verify: <smallest reliable test/build/check>
- Avoid: <repo-specific traps or risky commands>
```

</details>

## Token Efficiency

Cached input is repeated context. Uncached input is new context and usually the bigger savings target.

- Input: 2,737,243,381 tokens
- Cached input: 2,583,384,960 tokens
- Uncached input: 153,858,421 tokens
- Output: 10,115,197 tokens
- Cache ratio: 94.4%
- Uncached ratio: 5.6%
- Largest step: 243,511 input tokens of 258,400

Token-saving moves:

| Move | Confidence | First action |
|---|---|---|
| Use compact context artifacts | high | Add short project summaries and resume notes before asking Codex to reread long history. |
| Cap uncached context | high | Ask Codex to inspect the one most relevant file or search result first. |
| Route routine work to mini or medium | high | Choose mini or medium in the Codex UI/CLI for routine scans, reports, and formatting. |

## Project Mix

Where Codex spent the most work.

| Project | Sessions | Turns | User Messages | Tool Calls | Verification |
|---|---:|---:|---:|---:|---:|
| `project-a [redacted]` | 12 | 545 | 610 | 8,132 | 843 |
| `project-b [redacted]` | 16 | 224 | 276 | 2,813 | 639 |
| `project-c [redacted]` | 3 | 152 | 166 | 3,698 | 646 |
| `project-d [redacted]` | 2 | 71 | 73 | 1,069 | 339 |
| `project-e [redacted]` | 3 | 64 | 71 | 1,283 | 271 |

## Project Capsules

| Project | Pattern | Suggested AGENTS.md cue |
|---|---|---|
| `project-a [redacted]` | UI or browser verification | For long tasks in this project, keep a short durable checklist and validate files before resuming after compaction. |
| `project-b [redacted]` | UI or browser verification | For long tasks in this project, keep a short durable checklist and validate files before resuming after compaction. |
| `project-c [redacted]` | UI or browser verification | For long tasks in this project, keep a short durable checklist and validate files before resuming after compaction. |

## Instruction Playbook

Plain English: this checks whether your global custom instructions and project `AGENTS.md` files are helping Codex, getting stale, or leaking project-specific rules into every repo.

- Status: needs_review
- Files reviewed: 6
- Findings: 8
- Reviewable suggestions: 5

Top playbook findings:

- [medium] Project-specific preference may be global: stack, style, or workflow markers usually belong in a project `AGENTS.md`.
- [low] Many absolute rules: strong rules are useful, but too many can make Codex brittle across mixed tasks.
- [high] Potential secret in instruction file: move credentials to environment variables or a secret manager.
- [medium] Mode lock may be stale: a standing research-only or no-code rule can block implementation when the user expects action.
- [medium] Active project has no discovered `AGENTS.md`: a short playbook can prevent repeated context rebuilding.

Suggested playbook change:

```md
Keep global instructions about your communication and safety preferences. Put project stack, UI style, commands, and workflow rules in the relevant AGENTS.md.
```

## Prompt Quality

Short prompts are fine when context is obvious. If Codex guesses, add target, symptom, and success state.

| Category | Count |
|---|---:|
| Excellent | 151 |
| Good | 916 |
| Needs Work | 286 |

Prompt rewrites to try, shown with redacted previews:

- Score 4/10, missing action, target: `proceed with recommended fixes` -> `[Action] in [project/file] because [symptom or goal]. Success means [observable verification result].`
- Score 4/10, missing action, target: `sorry ide crashed. continue if not finished` -> `[Action] in [project/file] because [symptom or goal]. Success means [observable verification result].`
- Score 3/10, missing action: `okay proceed` -> `[Action] in [project/file] because [symptom or goal]. Success means [observable verification result].`

## Skill Opportunities

- `project-a [redacted]`: create a project workflow skill for the UI/browser verification loop.
- `project-b [redacted]`: capture context to gather, commands to verify, and resume rules after interruption.
- `project-c [redacted]`: turn repeated project setup steps into a reusable skill or local `AGENTS.md` playbook.

## Weekly Check-In

Optional. Codex app users can paste this to set a 7-day heartbeat. CLI/VS Code users can run `codex-coach report --since 7d` manually or use the installer's weekly schedule.

Recommended setting: `medium` intelligence for the routine weekly review; escalate only for risky or ambiguous findings.

<details>
<summary>Prompt to paste into Codex</summary>

```text
Set a weekly Codex Coach check-in every 7 days. Use medium intelligence for the routine review. Each week, run `codex-coach report --since 7d`, read `~/.codex-coach/reports/latest.md`, compare it with the previous report, and give me a concise TL;DR with the top 3 changes and exact next actions. Escalate to high only if the report shows security risk, production risk, repeated failures, or major architecture concerns.
```

</details>

## Expert Metrics

- Models: `{'gpt-5.5': 887, 'gpt-5.4': 230, 'gpt-5.4-mini': 49}`
- Efforts: `{'xhigh': 739, 'medium': 382, 'high': 45}`
- Tools: `{'exec_command': 14244, 'write_stdin': 2771, 'update_plan': 287, 'view_image': 151, 'browser_navigate': 36, 'browser_take_screenshot': 34}`
- Verification tools: `{'exec_command': 2107, 'update_plan': 156, 'browser_evaluate': 14, 'view_image': 13}`
- Errors: `{'error': 3608, 'failure': 532, 'failed': 405, 'timeout': 232, 'exception': 52}`

## Privacy

This report is generated from local Codex logs. Full prompt bodies and source code are not included by default.

