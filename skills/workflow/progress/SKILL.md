---
name: progress
description: >-
  Keeps one work ledger of the large work items in a multi-step task, and sends me a short
  progress and ETA report in chat each time an item changes state. Use it during a coding session
  or any long task that has several deliverables, whether you dispatch subagents or do the work
  yourself. Also use it when I ask for status, progress, an ETA, or what is left.
category: workflow
title: Progress
summary: >-
  Keeps a ledger of the large work items in a long task and sends a 12-line progress and ETA report
  each time one changes state. Items are never silently dropped or renamed. Scope changes are
  stated, and the ETA is always a range based on evidence. Works for one agent alone or for an
  orchestrator with subagents.
say: >-
  "Track progress on this and give me
  ETAs."
license: MIT
metadata:
  author: agentmemoir
  version: "1.0"
---

# Progress

One ledger, one report shape, one ETA rule. You always know what is done, what runs now, and how long the rest will take.

## Modes

- **Orchestrator:** you dispatch work items to workers (subagents). A worker report arrives, and you accept or reject it.
- **Solo:** you do the work yourself. When you finish an item and check it, that counts as an accepted report. "Dispatch" means you start the next item.

Everything below applies to both modes.

## The ledger

A work ledger is one list of all large work items. The ledger is the source of truth.

- A large work item is one deliverable. Do not list minor subtasks.
- Do not delete a work item. Do not rename a work item. Do not change the total without a stated reason.
- When scope changes, say so in the report: added, cancelled, abandoned, split, or merged.
- Mark a cancelled or abandoned work item with strikethrough. Keep it in the ledger. It does not count as progress. Leave it out of the ETA.
- Before each report, check your CLI's task or todo list against the ledger. If the CLI lost items, restore them from the ledger.

### Where the ledger lives

Use the first rule that applies:

1. My file location convention, if I have one.
2. Next to the plan file, with the plan's name and `.ledger.md` in place of `.md`. For example, `2026-10-22-cache-fix.md` gets `2026-10-22-cache-fix.ledger.md`.
3. If there is no plan file: `~/.agentmemoir/<owner>/<repo>/plans/<yyyy-mm-dd>-<short-slug>.ledger.md`. Read the owner and the repository name from `git remote -v`.

Rules for every location:

- If you write into a project folder, run `git check-ignore -q <path>` first. If it fails, the file would be staged, so use rule 3 instead.
- Never keep the only copy in a CLI's own folder, such as `~/.claude/todos/`. Session cleanup can delete it.
- The ledger file holds one line per item: `- [ ] <item>`, `- [x] <item>`, or `- [ ] ~~<item>~~ — cancelled: <reason>`. Update it before you send each report.

## When to report

- Send a report in chat when a work item changes state.
- Several state changes in a row get one report.
- Send nothing if no state changed since the last report.
- A blocked work item is a state change. Report it at once.
- Order: accept or reject the worker report, send the report, then dispatch the next work item.

## The report

At most 12 lines, not counting blank lines. Use these lines and headings, in this order. Start each heading line with its emoji.

```md
# <goal>
⏰ <range> remaining
📊 <accepted>/<total> done
📋 Scope: <n> large items. <change>

IN PROGRESS

🎯 <work item>
🎯 <work item> — blocked by <blocker>

NEXT

📦 <work item>

COMPLETED

✅ <work item>
✅ ~~<work item> — cancelled: <reason>~~
```

- `📊` counts accepted completed work items only. Cancelled and abandoned items do not count. The total leaves them out.
- `📋 Scope` appears only when the total or the item set changes. Name the change in a few words.
- `IN PROGRESS` holds the items that run now, plus every blocked item and its blocker.
- `NEXT` holds the one item that starts after the current items.
- `COMPLETED` holds the items accepted since the last report. Do not repeat earlier items. It also holds items cancelled or abandoned since the last report, with strikethrough and a short reason.
- Write `None` under a section that has no item. Keep its heading.

This shape replaces a prose status report. It is allowed even when other instructions cap reply length. At the end of the task, the final report follows your normal rules. Use the ledger as its source.

## The ETA

The ETA is a forecast, not a measurement. Report a range, such as `60–90 minutes`. Never report one number.

- Base the range on two facts: the unblocked work items that are left, and the time each item has taken so far. When the range changes, state that basis in one short line.
- Revise the range when new evidence arrives. A stale range is wrong.
- Forecast across unblocked work only. Leave out blocked, cancelled, and abandoned items.
- Write `⏰ unknown` when no evidence supports a range, for example before the first item finishes. Name the missing evidence on the same line.
- If scope changes, revise the range, or write `⏰ unknown` and name the missing evidence.

## Example

```md
# Ship the cache fix
⏰ 40–70 minutes remaining (2 items left, about 25 minutes each so far)
📊 2/4 done
📋 Scope: 4 large items. Split "tests" into unit and load tests.

IN PROGRESS

🎯 Version field on cache entries

NEXT

📦 Load test for concurrent writers

COMPLETED

✅ Stale-read reproduction test
```
