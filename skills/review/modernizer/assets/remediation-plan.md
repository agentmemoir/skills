# Remediation Plan: <project>

- **Repository:** <owner>/<repo>
- **Audit date:** <yyyy-mm-dd>
- **Plan date:** <yyyy-mm-dd>
- **Audit report:** `~/.agentmemoir/<owner>/<repo>/modernizer/<yyyy-mm-dd>-<short-slug>-audit.md`
- **Status:** <approved | partially approved | open items remain>

## 1. Executive decision summary

State the agreed priorities, the key tradeoffs, the scope, and the remaining uncertainty. Say what is approved, what is deferred, and what is out of scope.

## 2. Audit traceability

| Finding ID | Title | Priority | Evidence status | Confidence | Locations | Disposition |
|---|---|---|---|---|---|---|
| <ID> | <title> | <priority> | <verified / partial / unverified> | <confidence> | <file:line> | <approved / rejected / deferred / open> |

## 3. Decision register

| Finding ID | Options considered | Recommendation | Prism or "Decide and move on" | My decision | Rationale and remaining questions |
|---|---|---|---|---|---|
| <ID> | <options> | <choice> | <Prism / decide and move on> | <approved / rejected / deferred / open> | <reason and open items> |

Deferred decisions keep their risk, consequence, needed information, and trigger or deadline. An open item is never written as approved.

## 4. Target end states

| Technology | Current state | Approved target | Reason | Validated compatibility | Assumptions |
|---|---|---|---|---|---|
| <name> | <version or pattern> | <target> | <why> | <verified / assumed> | <assumptions> |

Distinguish validated compatibility from assumptions.

## 5. Phased roadmap

### Phase 0: Immediate security and operational risks

- <action and finding IDs>
- Prerequisites: <dependencies>
- Validation: <checks>
- Risks: <migration risks>

### Phase 1: High-priority compatibility and support remediation

- <action and finding IDs>
- Prerequisites: <dependencies>
- Validation: <checks>
- Risks: <migration risks>

### Phase 2: Planned dependency and framework upgrades

- <action and finding IDs>
- Prerequisites: <dependencies>
- Validation: <checks>
- Risks: <migration risks>

### Phase 3: Optional improvements

- <action and finding IDs>
- Prerequisites: <dependencies>
- Validation: <checks>
- Risks: <migration risks>

## 6. Actionable work items

### <Work item title>

- **Findings:** <IDs>
- **Steps:** <ordered steps>
- **Acceptance criteria:** <measurable conditions>
- **Suggested validation:** <tests or checks>
- **Estimated effort:** <low / medium / high / unknown>
- **Risks:** <risks>
- **Prerequisites:** <blockers>
- **Rollback or contingency:** <plan>

Repeat for each work item.

## 7. Dependency ordering

List blockers, coordination requirements, cross-cutting changes, and the recommended issue grouping or splitting. State which work items cannot start until another completes.

## 8. Explicit exclusions

- Rejected findings: <IDs and reasons>
- Invalid or duplicate findings: <IDs and evidence>
- Authorized deferrals: <IDs, risk, and trigger>
- Remaining evidence gaps: <what is unverified>
- Out-of-scope work: <items>

## 9. GitHub issue handoff

Mark every item **proposed** and **not yet filed**. Do not create issues from this section without the Level 4 approval.

| Proposed issue title | Finding IDs | Work item | Scope | Dependencies | Status |
|---|---|---|---|---|---|
| <title> | <IDs> | <work item> | <short scope> | <blockers> | proposed, not filed |
