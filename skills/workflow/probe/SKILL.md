---
name: probe
description: >-
  Grills me on a request before any code changes: restates my goal, explores avenues with
  research, settles every decision one at a time, then ends in a local implementation plan, a
  GitHub master issue with child issues, or a coding session. Use it when I say grill me, probe,
  interview me, plan this, think it through first, or before a feature, refactor, migration, or
  design change where a wrong guess is costly. Skip it for one-line fixes and questions that have
  a clear answer.
category: workflow
title: Probe
summary: >-
  Grills you on a request before any code changes, then turns the settled decisions into a plan,
  a GitHub master issue, or a coding session. Restates your goal, researches avenues, and asks one
  decision at a time. Costly choices go through prism. Plans and preferences are saved outside the
  CLI's data folder, so session cleanup cannot delete them.
say: >-
  "Probe me on the auth refactor before you touch any
  code."
license: MIT
compatibility: >-
  Needs a question tool for picks. The GitHub master issue path needs the gh CLI with sub-issue
  support (gh issue create --parent). Works best with the prism and progress skills installed.
metadata:
  author: agentmemoir
  version: "1.0"
---

# Probe

Decisions first, code second. Probe finds every decision a change needs, settles each one with me, and saves the result where the next session and every worker can read it.

## How you communicate with me

- **Use simple English (CEFR A2) and ASD-STE100**, including for security, design, and onboarding.
- **Be concise.** Start with the answer. No greeting or filler. Keep each reply to 1-4 lines, except for a restated goal, a prism decision, or a saved plan.
- **Never invent an answer to my question.** When my custom answer is unclear, do not guess what I meant and do not pick the closest option. Ask me again with the question tool, and say in one line which part of my answer was unclear.
- **A re-ask keeps the format of the question it repeats.** When the unclear answer belongs to a costly decision that was already put in the `prism` format, ask that decision again in the `prism` format: the same question, one option per lens, the pros and cons, and a recommendation. Mark the option I seemed to pick as **"Your previous choice"**, and never drop it. A plain approval question loses the trade-offs I am choosing between. For every other unclear answer, ask a plain clarification question. Prism is for choices, not for clarification.
- **Everything you post as me is mine.** An issue, PR, commit, comment, review, or label reads as my words. Never use one to talk to me. Read `references/github-issues.md` before you post anything.

## The skill's own folder

Probe keeps its files in `~/.agentmemoir/`. This folder is outside every CLI's data folder, so no session cleanup and no uninstall removes it. Use it for anything that must survive the session.

Read the owner and the repository name from `git remote -v`. For `github.com/agentmemoir/clio`, they are `agentmemoir` and `clio`.

| File | Holds |
|---|---|
| `~/.agentmemoir/<owner>/<repo>/plans/` | Plan files and saved master issue bodies. |
| `~/.agentmemoir/<owner>/<repo>/implementation-preference.md` | The ending chosen in Step 4. |
| `~/.agentmemoir/<owner>/<repo>/github.md` | Issue routing and the label mapping. See `references/github-issues.md`. |
| `~/.agentmemoir/progress-installation.md` | The record that I declined the progress skill. |

Never keep a record only in a CLI's own folder. Claude Code deletes `~/.claude/plans/` and `~/.claude/todos/` when it cleans up old sessions, and OpenCode keeps its data under `~/.local/share/opencode/`. A file there can vanish without warning. This rule holds for every CLI.

## Step 1: Clarify and confirm

1. When my request is unclear, stop and ask. Do not make a material assumption.
2. Restate my goal in your own words. Name the underlying intent, not only my words. Account for what I may not know or see in the codebase.
3. When the request concerns an environment or a host, say whose it is: the agent's own host, the target product's platform, or a user's machine.
4. Ask me to confirm your understanding, and wait.
5. After I confirm, use the question tool to ask how I want this session to end. If Step 4 saved a preference earlier, mark it as the default. Options:
   - Implementation Plan (local)
   - GitHub Master Issue (with child issues)
   - Coding Session
   - Not Decided Yet

"Not Decided Yet" is a normal answer here. Do not press me. My answer sets how deep you probe. It does not lock the ending: I choose again in Step 4.

## Step 2: Explore avenues

1. Before you offer avenues, research the question on the internet. Give the research to a background research subagent if your CLI has one; otherwise do it yourself. Reuse research already done for the same question.
2. Use the short evidence to improve my ideas, not to replace them.
3. Ask one concise question with the question tool, and offer actionable avenues for me to pick.

## Step 3: Probe before acting

- Once I pick an avenue, probe me on every decision and branch. Find every decision that must be made before coding or refactoring.
- Present one decision per message, and wait for my answer before the next one.
- Give concise options, with trade-offs where useful.
- When I must choose among real alternatives and the choice is costly to undo, use the `prism` skill format. If prism is not installed, use its gate anyway: only ask about costly choices.
- When one answer is clearly right, or the choice is cheap to undo, take it and tell me in one line. Do not ask.
- When a question concerns backwards compatibility, say so in the question in plain words: "This is a backwards-compatibility question."
- Do not begin implementation until every decision is settled and I tell you to proceed.

## Step 4: Confirm the next step

My Step 1 answer may have changed. Ask me again with the question tool, and use my new answer. Mark my Step 1 answer as the default, if it was not "Not Decided Yet". Otherwise mark the saved preference as the default. Options:

- Implementation Plan (local)
- GitHub Master Issue (with child issues)
- Coding Session

Do not offer "Not Decided Yet" here. The avenues are explored and the decisions are settled, so a plan, an issue, or code is the way to carry the work forward. If I refuse to pick, ask once more and say that the work cannot start without a decision.

Then save my pick in `implementation-preference.md` for the current repository. The file holds one line: the option name and today's date, for example `Coding Session 2026-10-22`. If I pick a different option next time, update the file.

### Implementation plan

- If I have a convention for implementation plans, follow it.
- If not, use the structure in `assets/plan.md`.
- Save it as *Where the plan file lives* says.

### GitHub master issue

- If I have a convention for master issues, follow it.
- If not, use `assets/github-master-issue.md` for the master and `assets/github-child-issue.md` for every child.
- Save a copy of the master body as *Where the plan file lives* says.
- The master holds the goal, the settled decisions, and the order of the work. The children hold the work.
- Follow `references/github-issues.md` for the repository, the labels, the sub-issue links, and the order of creation.

### Coding session

1. Save the full plan to a file before you change any code, as *Where the plan file lives* says. If you already saved it, keep that file. Do not write a second copy.
2. Report status with the `progress` skill. If it is not installed, follow *When the progress skill is missing*.

### When the progress skill is missing

The record is `~/.agentmemoir/progress-installation.md`. It holds one line: `declined YYYY-MM-DD`.

- Read that file first. If it holds a decline, do not ask. Report status with your own method, and say in one line that you did not ask because of the earlier decline.
- If there is no decline, ask me for permission to install it with `npx skills add agentmemoir/skills --skill progress --global -y`.
- If I approve, install it and use it.
- If I decline, report status with your own method, and write the file with today's date.
- If I approve later, install the skill and delete the file.
- If the file cannot be read or written, ask me as usual, and say that you could not record the answer.

### Where the plan file lives

The plan holds the settled decisions. Save it before any code change, so the session and every worker read the same decisions from the same place.

Use the first rule that applies:

1. My file location convention, if I have one.
2. `~/.agentmemoir/<owner>/<repo>/plans/`.

Rules for every location:

- Name the file `<yyyy-mm-dd>-<short-slug>.md`, so the date and the subject stay visible.
- If you write into a project folder, run `git check-ignore -q <path>` first. If it fails, the file would be staged, so use rule 2 instead.
- Do not keep the full plan in the conversation. Give the path to each worker that needs it, and read the file again when you need the plan.
- At the end of the session, ask me whether to move the plan into the project folder, keep it, or delete it.

## Step 5: Close the session

If the `retro` skill is installed, run it at the end of the session. If it is not installed, skip this step.

## Resources

- `assets/plan.md`: implementation plan structure. Load it in Step 4 for a plan or a coding session.
- `assets/github-master-issue.md` and `assets/github-child-issue.md`: issue body structures. Load them in Step 4 for a master issue.
- `references/github-issues.md`: rules for posting as me, the repository, labels, and sub-issues. Load it before any `gh` write.
