# Dependency, Supply-Chain, and Licence Reference

Load this file during Level 1 whenever the audit meets a package, toolchain, container, CI action, runtime, vendored library, or licence question, and again during Level 3 when a finding needs a retain, upgrade, replace, or migrate decision. It adds requirements to [audit.md](audit.md). It relaxes none of them, and it grants no permission to change the repository.

## 1. Find every dependency surface

A dependency surface is any place external code enters the build, the runtime, or the deployment. Enumerate every surface that exists, not only the obvious one:

- Manifests, lockfiles, workspace files, and private registry configuration.
- Direct, transitive, production, development, build, peer, optional, and platform-specific packages.
- Overrides, resolutions, patches, forks, git URLs, path dependencies, and substituted registries.
- Packages loaded by name at runtime: plugins, extensions, drivers, reflection targets, generated code.
- Packages declared but never imported, and packages imported but never declared.
- Language runtimes, system packages, and the base image a container builds on.
- CI actions, reusable workflows, and third-party pipeline steps.
- Compilers, build tools, toolchains, and pre-commit hooks.
- Infrastructure-as-code modules, providers, Helm charts, and deployment templates.
- Submodules, vendored source, and committed binaries.
- Model weights, datasets, fonts, icons, and other embedded third-party assets.
- Browser, mobile, desktop, editor, and IDE SDKs and extensions.

Record each surface as inspected, or list it as an explicit gap. Never report full coverage unless you can show how every surface was enumerated.

## 2. Record one row per dependency

Capture, for each dependency you assess:

- Name, ecosystem, surface, and whether it is direct or transitive.
- Resolved version, and the file that proves it.
- Purpose, and the dependency path that pulled it in.
- Licence, security state, trust state, and maintenance state.
- Inspection status.

Keep declared constraints separate from resolved versions. A constraint is not an installed version, and a manifest is not a lockfile. For a transitive problem, name the direct dependency whose upgrade would actually fix it; a finding the reader cannot act on is a finding poorly written.

## 3. Establish version facts

Record the installed version, the latest stable release, the latest version that carries the security fix, the release date, the supported release line and its end-of-life date, the runtime or framework versions the target requires, and the breaking changes between installed and target.

Prefer the smallest safe upgrade that removes the problem. The newest release is not automatically the safest or the most compatible, and a major jump needs a reason beyond novelty. When an ecosystem cannot pin an exact resolution, say so instead of guessing a number.

## 4. Establish security facts

Prefer sources in this order: vendor security bulletins, GitHub Security Advisories, OSV, NVD, ecosystem security databases, registry metadata, upstream announcements. Record the source, the URL, and the date you checked it.

For each advisory, record the identifier, severity and CVSS score where published, the affected version range, the fixed version, exploit maturity and known exploitation, the functionality affected, whether this codebase reaches it, and the fix or mitigation available.

Keep five questions separate, because they have different answers:

1. Is the package the subject of an advisory?
2. Is the resolved version inside the affected range?
3. Does this application use the affected functionality?
4. Is that use reachable from an exposed entry point?
5. Is the flaw exploited in the wild?

Never call a vulnerability fixed until you have compared the advisory ranges with the version you propose. An advisory does not prove exploitability, and a quiet scanner does not prove safety. When a scan tool cannot run under the read-only rule, say the check was not run rather than reporting it as clean.

## 5. Judge maintenance health

Look at release cadence, recent commit and contributor activity, how issues and pull requests are answered, documentation, downstream adoption, governance, security-disclosure practice, and how many maintainers stand behind the project.

Classify each project as actively maintained, maintained but low activity, slow-moving but stable, maintenance uncertain, deprecated, archived, abandoned, or end-of-life.

A mature project that ships rarely is not abandoned. Popularity supports a judgement; it never replaces one.

## 6. Judge supply-chain trust

Check for typosquatted and look-alike names, maintainer changes and handovers, account takeovers and compromised releases, malicious code and protestware, registry malware advisories, yanked, deprecated, or unpublished versions, install-time and postinstall scripts, unexpected network, filesystem, or credential access, obfuscated code and unexplained binaries, signing, checksums, and provenance attestations, dependency confusion between public and private names, lockfile integrity and drift, and CI secret exposure or cache poisoning.

Treat "suspected" as a state, not a verdict. Record the evidence, label it unresolved, and keep it visible. Never call a package malicious without evidence, and never clear a suspicion because a scanner was quiet.

## 7. Choose one recommendation

**A — Upgrade.** A viable package has a worthwhile safe update. Report current version, minimum safe version, preferred target, changes, breaking risk, migration steps, licence compatibility, and the tests needed.

**B — Replace.** The package is compromised, unfixable, unsafe, or unsuitable. Name the alternative, why it is better, the API and behaviour differences, compatibility risk, migration steps, and licence obligations.

**C — Migrate away.** The package is deprecated, archived, end-of-life, licence-incompatible, or unsuitable for long-term maintenance. Explain the risk, the replacement path, the effort, and the urgency.

**D — Retain.** The package is healthy, supported, secure, licence-compatible, and migration buys nothing. Say why, and name the trigger for the next review: an end-of-life date, a new advisory, a major release, or a support-policy change.

Every finding gets exactly one category. "A newer version exists" is not a reason, and neither is "other projects use it".

## 8. Clear a replacement candidate before recommending it

Rate the candidate's maturity: Tier 1 established adoption and security response, Tier 2 credible adoption with active maintainers and production use, Tier 3 emerging with real continuity risk. The tier is a risk statement, not a ranking.

Then investigate the exact candidate and version:

- Identity, version, and publication date.
- Security advisories, open security reports, and whether claimed fixes actually shipped.
- Regressions, compatibility reports, and data-corruption reports.
- Maintainer responses to the reports above.
- The full transitive licence graph, not just the package licence.
- Install-time scripts, build requirements, and native dependencies.
- Performance, bundle size, and resource impact.
- Provenance and release-integrity records.

Read the previous 90 days, plus older unresolved security reports. As a preference, choose a stable release with about 30 days of public exposure and read what was filed after it. Never delay a critical security fix to satisfy that preference.

Apply the outcomes honestly:

- No concerning reports: the candidate may pass.
- A newer version fixes a report: verify the fix, then assess that newer version.
- An unresolved concerning report: do not recommend it unqualified; look for another candidate.
- A vulnerable candidate: reject the affected versions unless a safe version or an accepted mitigation is verified.
- A disputed report: record an unresolved concern, not a vulnerability.
- A failed licence check: reject it, or send it to legal review.

If no candidate passes, say so. Keeping the current package with a documented plan is a legitimate recommendation.

## 9. Licence gate (blocking)

Licence compatibility blocks every A, B, and C recommendation. A secure, popular package is not automatically legal to use.

### 9.1 Read the real terms

Open the upstream licence file at the exact version, the licence field the manifest declares, and the registry entry. Compare all three, then run the same check across the transitive graph of the proposed state.

Record the SPDX identifier or expression, dual or multi licensing and which option applies to this version and this use, any change in terms between installed and target versions, custom or missing or contradictory terms, and files inside the project that carry a different licence.

A registry summary is metadata. It is not the licence.

### 9.2 Establish the distribution model

Ask exactly one question, at Level 3, the first time a decision needs it:

> How does this software reach people: a proprietary binary, a hosted service, internal-only use, open-source distribution, mobile or embedded software, a container image, or an SDK and library?

Wait for the answer. Do not issue an unqualified migration recommendation before you know it. If the answer is mixed, resolve the part that governs the package in front of you. Record the answer once in the plan and the decision file.

### 9.3 Classify the obligations

Classify the licence as permissive, weak copyleft, strong copyleft, network copyleft, source-available, proprietary, dual-licensed, or unknown or custom. Then state which obligations actually bind for this distribution model:

- Attribution and notice requirements.
- Source disclosure on distribution.
- Same-licence release of derivative work.
- Network-use disclosure.
- Linking and distribution restrictions.
- Patent and trademark terms.
- Data residency and cryptography rules.

Write the actual obligation. Do not use "viral" as a substitute for legal analysis. For GPL- and AGPL-family licences, name the version, say whether the use is linking, modification, or a network service, and name the clause that creates the duty.

### 9.4 Record and block

Record for every proposed change: current licence, target licence, transitive licence risks, distribution compatibility, copyleft flags, obligations, whether legal review is required, the decision, and the justification.

When an obligation is incompatible or uncertain, mark it **Licence risk: High / Blocked / Requires legal review**. Keep it out of the approved path, name compatible alternatives, explain the concern, and leave any waiver to a named person with legal authority.

Never claim licence compliance without opening the licence files, the version-specific terms, and the dependency graph.

## 10. Keep priority and licence separate

Use the severity model in [audit.md](audit.md), and keep these dependency-specific anchors:

- **Critical:** exploited in the wild, critical and exposed, or strongly suspected malicious.
- **High:** confirmed vulnerability with a fix, unsupported dependency with real exposure, unmaintained package on a sensitive path.
- **Medium:** deprecation without exposure, compatibility and maintenance problems, missing supply-chain controls, planned licence remediation.
- **Low:** non-security updates, unused packages, small technical debt.

Adjust with reachability, network exposure, asset value, compensating controls, and threat intelligence. A Low finding can still be licence-blocked. A security fix never clears a licence problem, and a licence problem never lowers a security priority.

For an accepted risk, record the description, justification, accountable owner, mitigation, review date, and expiry date. Never describe an accepted risk as resolved.

## 11. Review the governance that should catch this next time

Inspect the existing controls: vulnerability scanning, update automation, CI security and licence checks, SBOM generation and storage, exploitability records, alert routing and ownership, remediation deadlines, allow and deny lists, approved registries and pinning rules, licence policy and waiver records, waiver expiry, dependency-drift detection, review cadence, and sustainability checks on critical packages.

Report what is missing and recommend the smallest control that fixes it. Do not recommend a control the team cannot operate.

## 12. Add these sections to the audit report

Extend the inventory and findings with a dependency table:

| ID | Package | Ecosystem | Surface | Directness | Resolved version | Target | Security | Trust | Maintenance | Licence | Licence risk | Recommendation | Priority | Effort | Confidence | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

Then add a licence report covering incompatibilities, unknown licences, copyleft and network-copyleft exposure, transitive obligations, notice requirements, source-disclosure duties, legal reviews, approved waivers, and deferred licence decisions.

Two rules keep the table honest. Use `Unknown` instead of a guessed cell, and never let a blank cell imply that the check passed. Findings that could not be verified belong in the information-gaps section with the step needed to close them.

## 13. Export decisions when I ask for them

If I ask for a decision file, write it outside the repository to `~/.agentmemoir/<owner>/<repo>/modernizer/<yyyy-mm-dd>-<short-slug>-decisions.json`, following [the schema](../assets/dependency-decisions.schema.json) and the shape shown in [the example](../assets/dependency-decisions.example.json).

The file records what was found, what I decided, and what remains open. It never upgrades a status on its own: approved means I answered yes to that exact decision, deferred keeps its trigger, and blocked keeps its reason. Never place the file inside the audited repository.

## 14. Execution handoff

Modernizer never executes. When I approve implementation, the work leaves this skill and goes to a coding session, with me or another agent. Give that session this contract and nothing wider:

**Before changing anything:** confirm the exact package, ecosystem, installed version, approved target, the advisory it closes, the licence verdict, the affected dependency graph, the code changes implied, and the rollback.

**During the change:** update manifests and lockfiles through the ecosystem's own tool, follow the upstream migration guide, remove dead imports and obsolete workarounds, update third-party notices and SBOM and the inventory, then run formatting, static analysis, unit and integration tests, build and packaging checks, and the security and licence audits the project has.

**Never:** refactor unrelated code, remove behaviour, change a public interface for convenience, suppress or weaken a test, weaken a security or licence control, or bundle a second unapproved package into the same change.

**When verification fails:** stop, show the evidence, and ask. A failure is information, not permission to widen scope.

**Finish by:** inspecting the final dependency tree for unexpected additions, confirming rollback still works, and reporting only checks that actually ran and passed. If a check could not run, say which one and why.

## 15. Non-negotiables for dependency work

1. Never upgrade only because a newer version exists, and never pick a replacement for its popularity.
2. Never assume the latest version is the safest.
3. Compare advisory ranges with the proposed version before claiming a fix.
4. Verify a replacement's security, maintenance, trust, compatibility, and licence before recommending it.
5. Never call an open, unanswered report a confirmed vulnerability.
6. Never call a stable project abandoned because releases are rare.
7. Never make an A, B, or C recommendation that failed the licence gate.
8. Never present an assumption as verified, or a gap as coverage.
9. Never execute an approved change inside this skill, or a change I did not approve.
10. Never let a deferred, blocked, or accepted finding disappear from the record.
