---
name: retro
description: >-
  Reviews the skills, agent instructions, and rules a session used, and gives me up to three
  actionable suggestions grounded in what really happened: contradictions, ambiguities, and
  repeated workarounds. Use it at the end of a session, after a failed command, a confusion, a
  repeated workaround, or a conflict between two instructions, or when I ask for a retro, lessons
  learned, or what to improve in my skills or AGENTS.md. Honors an on/off switch I set once.
category: workflow
title: Retro
summary: >-
  Ends a session with up to three suggestions to fix your skills, agent instructions, and rules,
  each grounded in something that happened. Every suggestion names the file, quotes the
  instruction, and states the effect seen. One switch turns retros off for every future session.
say: >-
  "Run a retro on this
  session."
license: MIT
metadata:
  author: agentmemoir
  version: "1.0"
---

# Retro

Instructions drift. A retro catches the contradiction, the ambiguity, or the workaround the session hit, while the evidence is still in context.

## The suggestion switch

The switch is `~/.agentmemoir/suggestions.md`. This folder is outside every CLI's data folder, so session cleanup does not remove it. The file holds one line: `on YYYY-MM-DD` or `off YYYY-MM-DD`.

- Read the file first. If it holds `off`, do not review and do not offer suggestions. Stop here.
- If it holds `on`, review and offer suggestions. Do not ask me about the switch again.
- If the file does not exist, ask me whether to keep suggestions on or turn them off. Write the file with my answer and today's date.
- If I turn them off, skip the suggestions for this session too.
- If the file cannot be read or written, ask me, and say that you could not record the answer.
- To turn suggestions back on, write `on` and today's date. Deleting the file makes the next session ask again.

When I ask for a retro by name, run it even if the switch is `off`. The switch controls automatic retros only.

## When to run

- At the end of each session.
- After a failed command, a confusion, a repeated workaround, or a conflict between two instructions. Note it then, and report it at the end.
- When another skill, such as `probe`, tells you to run it.

## What to review

The skills, agent instructions (`AGENTS.md`, `CLAUDE.md`, and similar), and rules the session loaded.

- Report only actionable observations grounded in real events from this session.
- No speculation, no generic advice, no padding. If nothing qualifies, say `Suggestions: none.` in one line.

## The report

A `Suggestions:` section with up to three numbered items, most impact first. Each item gives:

1. The kind of fix: contradiction, ambiguity, missing rule, or stale rule.
2. The exact source paths.
3. The relevant instruction text, quoted or closely paraphrased.
4. The effect you saw in this session.

Do not change any file yet. If I pick a suggestion, settle the decisions with me first. Use the `probe` skill's Step 3 if it is installed. Then make the change.

## Example

```markdown
Suggestions:

1. Fix contradiction. `.agents/skills/<FOOBAR>/SKILL.md` asks design questions one at a time across turns, but `AGENTS.md` says to batch independent clarification questions in one question-tool call. These instructions conflict.

2. Clarify rule. The `prism` skill gate says to use it only when the choice is costly to undo. The session used it for a demo that only needed simple approval.

3. Fix ambiguity. `AGENTS.md` says the `noexec` skills apply to temporary storage that code creates, not to agent session notes. The ambiguity led me to treat `.workflow-feedback-implementation.json` as temporary, check it under `noexec`, and delete it.
```
