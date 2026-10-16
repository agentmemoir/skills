# Audit Report Template, Quality Checks, and Completion Criteria

Produce Markdown (this structure) plus one JSON finding per `finding.schema.json`. The two must agree on ids, severity, confidence, and status.

## Report structure

```markdown
# Security Audit Report

## Executive Summary
- Target, audit mode, date / audit id
- Findings by severity (Critical × N, Medium × N, Low × N)
- By confidence (confirmed / likely / suspected / rejected)
- Main areas covered; main limitations
- Never call the audit "comprehensive" unless coverage supports it.

## Investigation Scope
- Repo/target scope, included and excluded components
- Authorized testing boundaries, active-testing config, environments used
- Tools available vs. unavailable

## Findings

### SEC-001: Title
- Severity | Score | Confidence | Status | Category
- Attack surface, affected locations (verified file:lines)
- Root cause (concise)
- Expected behavior (the security property)
- Actual behavior (observed)
- Preconditions, impact (concrete), execution path
- Reproduction (case status and result)
- Evidence (source / test / command / external)
- Suggested remediation (actionable by me)
- Patch validation (exact status)
- Limitations (assumptions, missing evidence)

## Coverage Summary
- Categories and components investigated, agents used
- Test frameworks, static tools, dependency sources checked
- Areas not or partially investigated, with reasons

## Limitations and Open Questions
- Missing tools, unavailable environments, unverified assumptions
- Unexecuted cases, unresolved dependencies, unchecked references
- Config not available, findings needing my clarification

## Recommended Follow-Up
- Actions only, no automatic application (confirm prod config,
  provide isolated env, review a boundary, run a suite,
  upgrade a dependency after compat check, request a patch)
```

## Quality checks (coordinator runs before finalizing)

- Evidence: every finding grounded, locations verified, commands/tests reported as-run, references actually consulted, assumptions labeled.
- Validation: confirmed findings reproduced or sufficiently proven, independently challenged, mitigations checked, failed/blocked tests shown, severity consistent with confidence.
- Boundaries: testing authorized, external targets avoided unless approved, nothing destructive, secrets redacted, production files unchanged.
- Coverage: uncovered areas listed, missing tools recorded, framework assumptions named, scope honest.
- Output: Markdown⇄JSON consistent, ids unique, duplicates merged by root cause, rejected hypotheses retained when configured, patch statuses accurate, limitations included.

## Completion criteria

Complete when reconnaissance finished or explicitly blocked, capabilities detected, a plan created, relevant areas assigned, findings triaged and deduplicated, criticals independently challenged, reproduction attempted where practical, confidence honestly assigned, limitations recorded, the report generated, and no unauthorized production change made. Otherwise ship a partial report (done, blocked, evidence, supported findings, missing requirements, next steps) labeled partial.
