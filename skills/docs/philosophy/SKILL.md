---
name: philosophy
description: Researches a product before asking anything — product truths with evidence, hypotheses, and tensions between existing features — then interviews me and writes PHILOSOPHY.md at the repo root, then refactors AGENTS.md to enforce every product decision from those beliefs. Use it when I say write our philosophy, distill our principles, create a PHILOSOPHY.md, what do we believe, what are our guiding principles, or when I start a new product or repo and want its beliefs written down, or when the rules in AGENTS.md and my intent drift apart. Skip it for planning one feature or probing a code change (use probe), for one-line fixes, and for README or style-guide writing.
category: docs
title: Philosophy
summary: Researches your project before the first question — product truths with evidence, hypotheses, and tensions between existing features. Then interviews you one decision at a time, flags every contradiction the moment it appears, and recaps all choices so you can amend any answer. Costly forks go through prism with each option tagged as product truth or new proposal. Writes PHILOSOPHY.md only after your explicit confirmation, then refactors AGENTS.md so every rule names the belief it serves.
say: "Write our philosophy for this repo before you touch AGENTS.md."
license: MIT
compatibility: Needs a question tool for picks. Depends on prism for costly choices, probe for interview manner, and progress for research reporting. If one is missing, apply its gate anyway and report progress with your own one-line method.
metadata:
  author: agentmemoir
  version: "1.0"
  depends_on: [prism, probe, progress]
---

# Philosophy

Beliefs first, rules second. Philosophy builds the product's belief document from three sources: the truths already in the repo, the tensions between them, and the operator's decisions. It saves the result as `PHILOSOPHY.md` in the repo root and turns `AGENTS.md` into its enforcer. A philosophy that only describes never decides; every belief must rule something out.

## How you communicate with me
* **Use simple English (CEFR A2) and ASD-STE100**, also for abstract topics like beliefs and trade-offs.
* **Be concise.** Start with the answer. No greeting or filler. Keep each reply to 1-4 lines, except for findings reports, the full philosophy draft, and option blocks.
* **Full option text in the message.** Every option gets at least one complete line of text in the message body. The question tool only collects my pick. A label alone is never enough.
* **Plain words.** Define a term the first time you use it, and give one concrete example for every abstract question. If I say I do not understand, rewrite the question simpler; do not repeat it.
* **Never a forced pick.** I may skip any question or answer in my own words. Record the skip and bring it back in the recap.
* **Never invent an answer for me.** When my answer is unclear, do not guess and do not pick the closest option. Ask me again, and say in one line which part was unclear.
* **One decision per message.** Ask, wait, record, then move on.

## Reference skills
| Skill | Use it for |
| --- | --- |
| `prism` | Every costly fork in the interview: one short question, one option per lens, and a recommendation. Check its gate first. |
| `probe` | The interview manner: restate my goal, one decision at a time, settle every decision. This skill extends that manner from code changes to product beliefs. If I ask you to grill a code change, hand the work to `probe`. |
| `progress` | The research phase: one ledger of work items, a short report each time an item changes state, ETA as a range. |

If `prism` is not installed, do not stop: apply its gate yourself. If `progress` is not installed, offer to install it with `npx skills add agentmemoir/skills --skill progress --global -y`. If I decline, write `declined YYYY-MM-DD` to `~/.agentmemoir/progress-installation.md` — the same record probe reads — and report progress with your own one-line method.

## What this skill writes
| File | Holds | Written when |
| --- | --- | --- |
| `PHILOSOPHY.md` (repo root) | The product's core beliefs, hard lines, and boundaries. | Only after I explicitly confirm the final text. |
| `AGENTS.md` (repo root) | Rules that enforce the beliefs, each naming the belief it serves. | Only after `PHILOSOPHY.md` exists on disk. |

Never write either file earlier. If I abandon the session, write nothing.

## Step 1: Open and set expectations
1. Say what will happen, in order: research, interview, recap, draft, save, AGENTS.md.
2. Say why the document will hold: "I build this philosophy from three sources — the truths your project already holds, what I find in research, and your decisions."
3. Ask for patience, once: "Research comes first and can take a while. Step away if you like; I will report progress as I go."

## Step 2: Research the project
No interview question before this step is done.
1. Read broadly: README, docs, CHANGELOG, module and crate names, config files, tests, benchmarks, `git log --oneline -40`. A crate or module name is a truth too.
2. Extract **product truths**: what the project already is, does, or promises. Every truth carries a one-line evidence note (file, crate, or doc line). Reuse what the repo says; do not ask me for it.
3. Build **hypotheses**: candidate beliefs the repo already implies. A hypothesis is my reading, never yet a belief.
4. Detect **tensions**: places where truths pull against each other — a feature against a promise, a default against a claim, a rule the product itself would need to break. Name both sides and where they collide.
5. Work through the list with the `progress` skill: ledger items for each read pass, truths, hypotheses, and tensions; report on every state change.
6. Show me one findings block: truths, hypotheses, tensions. Keep it scannable.
7. Order the interview by tension: the sharpest tension is the first question.

## Step 3: Interview for beliefs
Cover these areas, starting from the tensions; adapt the order to the findings:
1. **Who it serves** — the primary user, and who it deliberately does not serve.
2. **What it optimizes first** — the one cost it accepts above others.
3. **Failure** — what the product does when it breaks: recover first, tell the truth first, or stop and ask first.
4. **Boundaries** — what the product is not, and what it will never do.
5. **Maintenance** — who carries the upkeep, and how much ritual the product may demand.
6. **Hard lines** — the rules that must never break, even under pressure.

Rules of the interview:
* One belief per message. Wait for my answer.
* After each answer, add it to a running numbered list of beliefs. Every 3-4 answers, show the list so I can correct course early.
* Push every belief until it forbids something. Ask: "What does this belief forbid?" A belief that forbids nothing is decoration. Cut it or sharpen it.
* When my answer is a slogan ("move fast", "user first"), ask what it forbids in this product. Rewrite it as a testable belief.
* **Never ask me to vote features into or out of identity.** That question has no true answer. Ask what the product refuses, where truths collide, and which cost it accepts instead.
* **Tag every prism option with its evidence.** `Truth:` when the repo already does this — name the file, crate, or line. `New:` when nothing in the repo does it yet. The recommendation names the truths it stands on.
* **Flag contradictions the moment they appear.** When my answer collides with a product truth or an earlier answer, say it then and there: one line for the collision, both sides quoted. Then reassure me: contradictions are normal, and fixing them now is what this document is for. Offer three ways out: extend the truth, change the truth, or scope an exception. Record the resolution.
* **Scope every hard line.** State what is forbidden, under what condition, and who consents. Never a blanket ban. Test each hard line: if the product itself could ever legitimately need to do the thing, scope it tighter.
* When a fork is real and costly to undo, use the `prism` format. When one answer is clearly right or cheap to undo, take it and tell me in one line. Do not ask.
* These are my beliefs, not yours. Collect, sharpen, and challenge. Never supply.

## Step 4: Recap and amend
1. Show every decision and my answer, numbered. Include the questions I skipped.
2. Ask with the question tool: Amend an answer / Recap walkthrough / Proceed to draft.
3. *Amend an answer*: I name the number. Re-ask that one decision. My previous choice appears as one option labeled **"Your previous choice"** — never dropped, never buried. New options may join it.
4. *Recap walkthrough*: walk the list one decision per message, same rule for each.
5. When nothing is left to amend, move on. Update the belief list with every change.

## Step 5: Draft and display
1. Assemble `PHILOSOPHY.md` from [assets/philosophy-template.md](assets/philosophy-template.md), filled with my answers. Keep it short: every belief earns its place by deciding a real disagreement.
2. Resolve every tension from research inside the draft: as a belief, a hard line, a boundary, or an explicit precedence. If one is still open, settle it before drafting.
3. Show the full document in the conversation. Write no file yet.
4. Ask me to mark every line that is wrong, soft, or missing. Fix, re-show, and repeat until I say it reads right.

## Step 6: Confirm and save
1. Ask with the question tool: Save PHILOSOPHY.md / Edit more / Abandon.
2. Write `PHILOSOPHY.md` only on an explicit "Save". A change request, silence, or a new topic is not a yes.
3. Save to the repo root. This file is the product's constitution: it lives with the code, not in a user folder.
4. If I abandon, stop. Write nothing, and do not touch `AGENTS.md`.

## Step 7: Refactor AGENTS.md
1. Read `AGENTS.md` if it exists. If not, plan to create it from [assets/agents-template.md](assets/agents-template.md).
2. Rewrite it so it enforces the philosophy:
   * Start with one line of authority: "When this file and PHILOSOPHY.md disagree, PHILOSOPHY.md wins."
   * Every product-decision rule names the belief it serves, for example: "Recover before reporting (Philosophy 3)."
   * Keep rules that are not product decisions — build commands, test commands, code style — untouched.
   * For product rules that fit no belief, list them to me and propose: extend the philosophy, or drop the rule. Never delete one silently.
3. Show me the refactored `AGENTS.md`, then save it. Report in one line that `PHILOSOPHY.md` and `AGENTS.md` are now in force.

## The test
* A belief passes if it would decide at least one real disagreement.
* A hard line passes if it states what is forbidden, under what condition, and who consents.
* A tension passes if the document resolves it.
* A rule in `AGENTS.md` passes if it names the belief it serves.
* The document passes if a stranger could predict the product's behavior from it alone.

## Worked example
```
You: Research done. 14 truths, 2 tensions. Sharpest tension: clio-backup copies the
     store, but the README promises nothing leaves the machine. We start there.
Me: Backup should just work, even to my own server.
You: That collides with a truth: "offline by default" (README, Setup Modes). Not a
     problem — contradictions are what this document is for. Three ways out:
     backup stays local (extend), nothing ever leaves (change), backup may leave
     only to targets I named (scope).
Me: Scope it.
You: Recorded: "No upload without permission." Next fork, prism this. Curation must
     live somewhere. Fix where?
     Option 1 (Speed): admit everything, curate at read. [New]
     Option 2 (Reliability): admit at write, hygiene prunes later, backup before
     every prune. [Truth: clio-admission, clio-hygiene, clio-backup]
     ...
     Recommendation: Option 2 — it stands on three truths you already ship.
...
You: Recap before drafting. Decision 3 was curation at write. Re-ask?
Me: Yes, re-ask 3.
You: Option 1 (Speed): admit everything, curate at read. [New]
     Option 2 (Reliability): admit at write, backup before prune. [Truth: ...]
     Option 3 (Simplicity): strict fixed caps, no hygiene. [New]
     Your previous choice: Option 2 (Reliability).
```

## Resources
* [assets/philosophy-template.md](assets/philosophy-template.md): the PHILOSOPHY.md structure. Load it in Step 5.
* [assets/agents-template.md](assets/agents-template.md): the AGENTS.md structure. Load it in Step 7.
