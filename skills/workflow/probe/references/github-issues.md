# GitHub Issues

Rules for how you work with GitHub issues and pull requests. Read this before any `gh` write.

## An issue or PR is a record, not a channel

You post with my account. An issue or PR body, a commit, a comment, a review, a reply, and a label all read as my words. Write each one for whoever finds the thread next.

- **Never refer to me in the third person.** Not "the operator", not "the maintainer", not "the owner".
- **Never use a post to reach me.** No status notes, no questions, no "ready for review" notices, no approval requests, no announcements, no answers. A post that tells me something is me talking to myself. Put all of it in the conversation.
- **Never stage a question in an issue or PR.** A post can end with options and a recommendation. It cannot end with a request for a decision from someone who is not reading it.
- **If you need an answer, ask me in the conversation.** Then record my answer in the issue as a decision, with its date, so the next reader sees what was chosen, not only what was on the table.

The failure this prevents is quiet. The post reads as though someone else is being consulted, so nobody notices that the question never reached me.

## Commands

You run `gh` inside a clone. It picks the repository from `git remote -v`. Use a heredoc or `--body-file` for multi-line bodies.

| Task | Command |
|---|---|
| Create | `gh issue create --title "..." --body-file <file> --label "<type>" --label "<area>" --label "<difficulty>"` |
| Read | `gh issue view <n> --comments --json title,body,labels,comments` |
| List | `gh issue list --state open --json number,title,labels` with `--label` filters |
| Comment | `gh issue comment <n> --body "..."` |
| Label | `gh issue edit <n> --add-label "..."` or `--remove-label "..."` |
| Replace body | `gh issue edit <n> --body-file <file>` |
| Close | `gh issue close <n> --comment "..."` |

Issues and pull requests share one number space, so a bare `#42` may be either. Run `gh pr view 42` first, then fall back to `gh issue view 42`.

For pull requests: `gh pr view <n> --comments`, `gh pr diff <n>`, `gh pr comment`, `gh pr edit --add-label` or `--remove-label`, and `gh pr close`.

## Repository routing

File the issue in the repository that holds the subject.

1. If the project has its own issue-tracker rule that maps subjects to repositories, follow it.
2. Otherwise read `routing:` in `~/.agentmemoir/<owner>/<repo>/github.md`.
3. Otherwise ask me which repository holds the subject, and save my answer there.

## Labels are mandatory

Every issue you file carries all three kinds of label, including a master issue that only holds other issues. Tools that pick up work read labels, so an issue without them is unfinished.

| Kind | How many | Meaning |
|---|---|---|
| Type | Exactly one | What kind of change: bug, enhancement, documentation, and so on. |
| Area | At least one | The parts of the system the change touches. |
| Difficulty | Exactly one | Effort and risk, as an ordered set. |

The difficulty set is ordered. The lowest tier is a small, local fix. The middle tier needs care inside one area. The highest tier spans areas, needs a design decision, or is nondeterministic. If the repository names its tiers differently, the order carries the same meaning.

- Attach the labels in the create command. Use the repository's real label names, not the kind names.
- Apply `good first issue` only with the lowest difficulty label, and only if the repository defines it.
- A name outside the repository's label set is a defect in the filing.

### Finding the label names

1. Read `labels:` in `~/.agentmemoir/<owner>/<repo>/github.md`.
2. If it is missing, run `gh label list --json name,description --limit 200` and map the names to the three kinds.
3. If a kind has no clear match, ask me once. Offer two choices: map existing labels to that kind, or create the missing labels with `gh label create`. Never create labels without my approval.
4. Save the result in `github.md`, so you do not ask again.

The file uses this shape:

```yaml
routing:
  default: agentmemoir/clio
  # subject: owner/repo, only when subjects live in other repositories
labels:
  types: [bug, enhancement, documentation]
  areas: [area:cli, area:store, area:retrieve]
  difficulties: [difficulty:easy, difficulty:medium, difficulty:hard]  # ordered, lowest first
  good_first_issue: "good first issue"  # optional
```

If the file cannot be read or written, ask me as usual, and say that you could not record the answer.

## Master and child issues

The master holds the goal and the settled decisions. Its children hold the work.

Create them in this order. The master holds the order of the work, so its numbers must be right.

1. Create the master with the placeholder child list.
2. Create each child with `--parent <master>`. Add `--blocked-by <numbers>` when a child must wait for another.
3. Replace the master body with the real child numbers and titles: `gh issue edit <master> --body-file <file>`.

| Task | Command |
|---|---|
| Create a child | `gh issue create ... --parent <master>` |
| Link an existing child | `gh issue edit <master> --add-sub-issue <child>` |
| Unlink a child | `gh issue edit <master> --remove-sub-issue <child>` |
| Block a child | `--blocked-by <numbers>` on create, `--add-blocked-by <numbers>` on edit |
| List the children | `gh issue view <master> --json subIssues,subIssuesSummary` |

Where the repository has no sub-issues, or `gh` does not support `--parent`, keep the `Master issue:` and `Blocked by:` lines from the child template in the child body. Delete the `Master issue:` line when sub-issues work.
