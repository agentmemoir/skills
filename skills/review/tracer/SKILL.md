---
name: tracer
description: Audit a local codebase for security vulnerabilities with evidence-based findings. Use when I ask to find security bugs, audit for vulnerabilities, check auth, injection, secrets, crypto, dependencies, or business-logic flaws, or want reproducible proof and severity-rated reports. Read-only by default; never modifies production code or tests external systems without explicit approval.
---

# Tracer

A language-agnostic security audit of a local repository. It maps the attack surface, investigates reachable vulnerabilities, reproduces them safely, challenges each hypothesis independently, and reports severity-rated findings with honest limits. Evidence beats speculation at every step.

## When to use

Run this skill when I ask to audit code for security issues, review auth, injection, secrets, crypto, dependencies, configuration, or business logic, or validate a suspected vulnerability. Skip it for prose, general bug hunts without a security angle (use `review`), and one-line fixes.

## Non-negotiables

1. **Read-only by default.** Read files, inspect config, run safe analysis, create isolated reproduction cases, and suggest patches as diffs. Never modify production sources, apply patches, delete files, rotate credentials, change infra, or contact external systems without a separate explicit request.
2. **No invented evidence.** Never claim a command ran, a test passed, a bug reproduced, an advisory applies, or a line exists without verifying it. Missing tool = stated limitation. Incomplete evidence = lower confidence, not stronger wording.
3. **Authorized targets only.** Default target is the local repo and its test fixtures. Never test external hosts, third-party services, or production systems unless I name the target and scope explicitly. Prefer harmless proofs: dummy identities, synthetic data, temp dirs, mocks, bounded inputs. No real credentials, no destructive payloads, no persistence, no DoS.
4. **Redact secrets.** Findings, handoffs, logs, and reports carry secret type and location, never values. Use `[REDACTED_API_KEY]`-style placeholders.

## Workflow

Work the phases in order. On a small repo, one pass covers several; on a large repo (>50 files), scope to the highest-risk subsystem first (auth, data layer, public endpoints). Tell me the plan and scope up front.

### Phase 1 — Initialize and detect capabilities

Record audit id, target path, mode, available vs. missing tools (shell, tests, analyzers, package managers, advisory DBs, git history, containers, network), and known limits. Gracefully degrade when tools are missing. See `references/configuration.yaml` for defaults.

### Phase 2 — Reconnaissance

**Read:** `agents/reconnaissance.md`. Map languages, frameworks, entry points, public vs. internal interfaces, authN/authZ controls, input/output boundaries, data stores, crypto, file/process/network operations, dependency manifests and lockfiles, test setup, and trust boundaries. Output the repository map (shape in the agent file). Distinguish verified facts from inferences.

### Phase 3 — Threat modeling

**Read:** `agents/threat-modeling.md`. Identify assets, actors (unauthenticated, authenticated, cross-tenant, low-privilege, admin, services, workers), trust and privilege boundaries, data flows, sensitive operations, assumptions, controls, abuse cases, and failure modes. Prioritize reachable attack paths over generic checklists. Update the model as evidence arrives.

### Phase 4 — Plan and discover

Split the repo into investigation units covering all 14 categories in `references/investigation-categories.md` (authentication, authorization, injection, input validation, file/path handling, secrets, cryptography, data protection, serialization/parsing, dependencies, configuration/infrastructure, business logic, concurrency/resources, error handling/observability) and assign per risk, not per category — small repos get fewer, broader units. Each unit states scope, files, threat assumptions, questions, tools, budget, output format, and prohibitions. **Read:** `agents/security-specialist.md`. Category checklists live in `references/investigation-categories.md`. Every hypothesis records root cause, code path, boundary, preconditions, impact, evidence have/need, and a safe reproduction plan.

### Phase 5 — Reproduce safely

**Read:** `agents/bug-case-writer.md`. Convert each hypothesis into a minimal case using the repo's own test framework and fixtures (standalone script or harness only if none exists). Each case states the security property, preconditions, setup, trigger, expected vs. actual result, impact, cleanup, temp/permanent status, and execution result. `created_not_executed` is never proof.

### Phase 6 — Validate independently

**Read:** `agents/validator.md`. A fresh pass challenges every hypothesis: is the code reachable, the input attacker-controlled, the boundary crossed, a mitigation present elsewhere, the behavior intentional, the severity justified, the bug a duplicate? Critical findings pause lower-priority work until validated or blocked. Confidence follows the evidence standard below.

### Phase 7 — Report, then stop

Write the Markdown report plus one JSON finding per `references/finding.schema.json` (template: `references/audit-report.md`). Run the quality checks (evidence, validation, boundaries, coverage, output integrity) and state completion or blocked-partial explicitly — never present partial work as complete. Patches are suggestions only, generated on request: **Read:** `agents/patch-agent.md`. Then stop and wait for my instructions.

## Scoring and confidence

| Severity | Score | Meaning |
|----------|-------|---------|
| Low | 1 | Minor weakness, edge case, low-impact inconsistency |
| Medium | 5 | Functional weakness, meaningful exposure, integrity issue |
| Critical | 10 | Auth bypass, sensitive exposure, destructive impact, severe crash |

Score is internal prioritization, not CVSS. Base severity on impact, exploitability, privileges, exposure, assets, and mitigations — never on how suspicious a pattern looks.

| Confidence | When |
|------------|------|
| Confirmed | Behavior verified, path reachable, preconditions set, impact shown, mitigations checked, reproduction passed or static proof sufficient |
| Likely | Strongly supported, one runtime/environment condition unverified, missing evidence named |
| Suspected | Suspicious pattern, plausible impact, reachability or mitigations unknown |
| Rejected | Absent, mitigated, unreachable, wrong assumption, or intentional without property violation |

Lifecycle: `discovered → triaged → investigating → validated → reported`, with `partially_validated` or `rejected` exits from investigating, and `patch_requested → patch_generated → patch_validated|patch_unvalidated` after reporting. The coordinator (`agents/coordinator.md`) owns state, dedup (`SEC-001…` by root cause and remediation, never by file alone), and escalation.

## Outputs and references

- `agents/` — coordinator, reconnaissance, threat-modeling, security-specialist, bug-case-writer, validator, patch-agent prompts.
- `references/configuration.yaml` — audit defaults (mode, targets, validation, bug cases, patches, dependencies, secrets, output).
- `references/finding.schema.json` — final finding contract (`score` matches severity: 1/5/10; `null` for unknowns, never guesses).
- `references/handoff.schema.json` — agent handoff, evidence, and hypothesis shapes.
- `references/investigation-categories.md` — the 14 category checklists (auth through error handling).
- `references/audit-report.md` — report structure, quality checks, completion criteria.
- `references/examples/` — confirmed, suspected, and rejected finding examples.
