---
name: prism
description: >-
  Formats a costly decision for me as one short question, one option per lens (Speed,
  Simplicity, Reliability, Flexibility), and a recommendation. Use it only when no option is
  clearly best, the choice is expensive to undo (money, data, public API, security, user trust,
  or more than a day of rework), and the choice needs my judgment. Do not use it for planning or
  clarification questions, demos, or choices that are cheap to undo.
category: workflow
title: Prism
summary: >-
  Puts a costly, hard-to-undo decision to you as one short question, one option per lens, and a
  recommendation. Speed, Simplicity, Reliability, and Flexibility each get an option that fully
  solves the problem, with real pros and cons. If a choice is clear or cheap to undo, the agent
  makes it and tells you in one line.
say: >-
  "Prism this: which cache fix should we
  ship?"
license: MIT
metadata:
  author: agentmemoir
  version: "1.0"
---

# Prism

A costly choice gets one decision format: one question, one option per lens, and a recommendation. You can then compare the options and pick one quickly.

## The gate

Use this format only when all three are true:

1. No option is clearly best.
2. Undo is expensive: money, data, public API, security, user trust, or more than a day of rework.
3. The choice needs my judgment.

If the gate is not met, decide, act, and tell me in one line. Or ask for simple approval. Do not use this format.

## When to use it

- One answer is clearly right, or the choice is cheap to undo: take it and tell me in one line. Do not ask.
- Before you ask, try to make the choice reversible, smaller, or staged. If you can, do that and report it in one line.
- Demo, example, suggestion, or feedback request: do not use this format. Ask for simple approval.
- Planning and clarification questions: not covered here. Use your CLI's native question tool.
- One decision per message.
- If a question tool limits the number of options or the label length, put the full text in the message. Use the tool only to collect my pick.

## Part 1: Question

One or two sentences, 24 words max, CEFR A2 English. State the problem.
Add why we must decide now only if there is a real deadline or cost of waiting.

Bad: "Given the current architecture, should we consider refactoring the module to improve maintainability?"
Good: "The cache holds stale data after a write. Pick a fix now, or the release ships wrong data."

## Part 2: Options

Consider the lenses in this order: Speed, Simplicity, Reliability, Flexibility. Title each option "Option N (Lens): <approach>".

- Give each lens its own option. Never merge two lenses into one option.
- Every option fully solves the problem in the question and stands alone.
- 2-3 pros and 2-3 cons, about 10 words each. Cons are real costs.
- When a lens has no real approach of its own, write the option that best serves that lens and say in one line why it is weak.
- When the best option for a lens is the same approach as another lens's option, drop that lens. Say in one line which lens you dropped and which option covers it. Never send two options with the same approach. So you send three or four options.
- Project terms are fine. Keep sentences A2.

## Part 3: Recommendation

"Recommendation: Option N (Lens)." Then "Why:" one or two sentences on the fact in this situation that decides it. The lens order is a checklist, not a ranking. Any lens can win.

## Before sending

- The gate is met: no clearly best answer, expensive to undo, needs my judgment.
- You tried a reversible, smaller, or staged choice first.
- The question is 24 words or fewer.
- Every lens has its own option, or a one-line note on why it was dropped as a duplicate.
- No two options use the same approach.
- Every option has pros and cons and solves the stated problem.
- The recommendation and its reason are present.

## Worked example

```md
The cache holds stale data after a write. Pick a fix now, or the release ships wrong data.

Option 1 (Speed): clear the whole cache on every write.
- Pros: one line of code; ship today; no new part.
- Cons: slow reads on a large cache; throws away warm data.

Option 2 (Simplicity): drop only the changed key on each write.
- Pros: one config change; easy to read; no new part.
- Cons: more database reads; a small stale window stays.

Option 3 (Reliability): tag each entry with a version and drop stale ones.
- Pros: no stale reads; handles concurrent writes; predictable under load.
- Cons: more code; needs a version field in every entry.

Option 4 (Flexibility): write through the cache and refresh in the background.
- Pros: fastest reads; scales with load; easy to add more cache rules later.
- Cons: most work; adds a worker to run and watch.

Recommendation: Option 3 (Reliability).

Why: it removes stale reads and stays predictable when two writers race, and it costs less to build than Option 4.
```
