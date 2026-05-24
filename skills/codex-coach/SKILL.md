---
name: codex-coach
description: Use when the user asks to analyze their Codex usage, habits, prompt quality, model/effort choices, tool usage, project switching, context recovery, or wants suggestions for Codex custom instructions or AGENTS.md improvements.
---

# Codex Coach

Codex Coach is a local-first coaching workflow. Use the bundled `codex-coach` command for deterministic parsing; do not manually scan large logs unless the command is unavailable.

## Quick Workflow

1. Run a health check:

```sh
codex-coach doctor
```

2. Generate or refresh the report:

```sh
codex-coach report --since 7d
```

3. Use beginner or expert mode based on the user:

```sh
codex-coach report --since 7d --mode beginner
codex-coach report --since 7d --mode expert
```

4. Read `~/.codex-coach/reports/latest.md` and summarize the highest-impact findings.
   When mentioning generated files in chat, format them as clickable absolute Markdown links, for example:
   `[latest.md](/home/example/.codex-coach/reports/latest.md)`.

5. For config improvements, generate review files:

```sh
codex-coach suggest-config --since 7d
```

6. For custom instructions or `AGENTS.md` health, run the playbook audit:

```sh
codex-coach instructions report --since 30d
codex-coach instructions suggest --since 30d
```

7. For a prompt the user is drafting, lint it directly:

```sh
codex-coach lint-prompt "fix the login bug"
```

8. Explain that suggestions are reviewable and are not applied automatically.

## User Modes

- Beginner: summarize the top 3 findings in plain language, then give one habit to try this week.
- Expert: include model/effort mix, tool mix, verification ratio, compactions, project capsules, and skill opportunities.
- Project-specific: if the user names a project path, filter your discussion to that project from the report/facts if present.

## What To Surface

- Report files: include clickable absolute Markdown links for `latest.md`, the dated weekly report, and `latest.json` when those files were generated.
- Project capsules: explain the likely workflow, top friction, and suggested local instruction.
- Prompt rewrites: show the redacted preview and the safer template, not the raw original prompt.
- Confidence: keep low-confidence suggestions tentative; high-confidence suggestions can be presented as the next best habit.
- Skill opportunities: if the report flags a repeated workflow, suggest a small user skill with trigger, context to gather, verification commands, and resume rules.
- Instruction Playbook: surface stale mode locks, project-specific global rules, missing project playbooks, missing verification cues, and secret-shaped values without quoting raw instruction text.

## Guardrails

- Keep reports local. Do not upload logs.
- Do not paste full prompt bodies or source code into chat.
- Treat `~/.codex-coach/facts/latest.json` as the machine-readable source of truth.
- Do not edit global custom instructions or `AGENTS.md` automatically; show the generated suggestion file and ask for explicit approval before applying any change.

## Optional References

- Read `references/prompt-rubric.md` when explaining prompt quality scores.
- Read `references/config-suggestions.md` when discussing custom instruction or AGENTS.md changes.
- Read `references/privacy.md` when the user asks what data is read or stored.
