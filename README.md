# Codex Coach

![Codex Coach banner](assets/brand/codex-coach-banner.png)

Codex Coach is a local-first usage coach for Codex users. It reads Codex session logs on your machine, generates redacted habit reports, and suggests reviewable improvements to your Codex configuration and project instructions.

## Install

With npm:

```sh
npm install -g codex-coach
codex-coach install
```

From a checkout:

```sh
./install.sh
```

Windows PowerShell:

```powershell
.\install.ps1
```

The installer adds the `codex-coach` command when possible, copies the Codex plugin/skill into your local Codex plugin directory, and writes a default config under `~/.codex-coach/`.

Install options:

```sh
./install.sh --weekly       # default weekly report
./install.sh --daily        # opt-in daily scheduled report
./install.sh --no-schedule  # manual-only
```

```powershell
.\install.ps1 -Daily
.\install.ps1 -NoSchedule
```

## Use

```sh
codex-coach doctor
codex-coach scan --since 7d
codex-coach report --since 7d
codex-coach report --since 7d --mode expert
codex-coach suggest-config
codex-coach instructions scan --since 30d
codex-coach instructions report --since 30d
codex-coach instructions suggest --since 30d
codex-coach lint-prompt "fix the failing auth test and verify pytest passes"
```

Inside Codex, ask:

```text
Coach my Codex usage
Show my weekly Codex Coach report
Suggest custom instruction changes
```

## Privacy Model

- Local only by default.
- Reads `~/.codex/sessions/**/*.jsonl` and `~/.codex/archived_sessions/*.jsonl`.
- Reports do not include full prompt text or source code.
- Suggestions are written as review files and are never applied automatically.

## Outputs

- `~/.codex-coach/reports/latest.md`
- `~/.codex-coach/reports/weekly-YYYY-MM-DD.md`
- `~/.codex-coach/facts/latest.json`
- `~/.codex-coach/facts/report-latest.json`
- `~/.codex-coach/instructions/index.json`
- `~/.codex-coach/suggestions/*.patch.md`

## Coaching Features

- Project capsules: redacted per-project workflow summaries with suggested local instructions.
- Prompt rewrites: safe templates for vague prompts without storing full prompt text.
- Confidence-scored suggestions: low, medium, or high confidence improvement notes.
- TL;DR action plan: beginner-friendly changes with where to make them, whether they belong in settings, a prompt, or `AGENTS.md`, and exact Markdown snippets.
- Since Last Report: a small Markdown trend panel comparing the current report with the previous report baseline.
- Token efficiency: cached vs uncached input, output, routing, and context-budget recommendations.
- Beginner and expert report modes.
- Skill opportunities: repeated workflow patterns that may deserve a reusable Codex skill.
- Real-time prompt linting through `codex-coach lint-prompt`.
- Instruction Playbook Audit: review global custom instructions and project `AGENTS.md` files for stale mode locks, scope leaks, missing verification rules, secrets, and active projects without a playbook.

## Brand Assets

- Main README banner: `assets/brand/codex-coach-banner.png`
- Wide logo/social preview: `assets/brand/codex-coach-logo.png`
- Square icon: `assets/brand/codex-coach-icon.png`
