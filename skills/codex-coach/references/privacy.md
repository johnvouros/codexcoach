# Privacy Model

Codex Coach is local-first.

Default inputs:

- `~/.codex/sessions/**/*.jsonl`
- `~/.codex/archived_sessions/*.jsonl`
- Optional Codex config, global instruction files, and project `AGENTS.md` metadata for Instruction Playbook Audit.

Default outputs:

- `~/.codex-coach/facts/latest.json`
- `~/.codex-coach/reports/latest.md`
- `~/.codex-coach/reports/weekly-YYYY-MM-DD.md`
- `~/.codex-coach/instructions/index.json`
- `~/.codex-coach/suggestions/*.patch.md`

Default redaction:

- Full prompts are not written to Markdown reports.
- Source code is not included.
- File paths, URLs, emails, secret-like tokens, and long opaque strings are replaced in previews.
- Prompt rewrites are generated as generic templates and do not include raw private details.
- Project capsules use redacted project labels instead of full local paths.
- Config suggestions are written as review files and are not applied automatically.
- Instruction audits store hashes, sizes, categories, and suggested snippets; they do not write raw instruction file bodies to reports or facts.
