# Prompt Quality Rubric

Codex Coach scores prompts from 0 to 10 using local text only.

- Excellent: clear action plus enough context, or a brief reply that is unambiguous because the previous Codex turn asked for a choice.
- Good: actionable but missing one optional detail.
- Needs work: too short to identify the target, missing the failing symptom, or using vague words like "fix", "run", "delete", or "make better" without context.

Do not treat brevity as bad by itself. Brief prompts like "yes", "proceed", "run tests", or "commit" can be high quality when Codex has enough local context.

When recommending improvements, prefer templates:

```text
[action] in [project/file] because [symptom]. Success means [observable result].
```

```text
Debug [error text]. I expected [expected behavior], but got [actual behavior].
```

`codex-coach lint-prompt "..."` applies the same rubric to a single draft prompt. If the score is low, present the suggested rewrite as a template, not as a claim that Codex Coach knows the missing private details.
