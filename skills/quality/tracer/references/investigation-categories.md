# Investigation Categories

Combine categories when a code path spans them, but record which ones were covered. Each item is a prompt to check reachability and exploitability in context — never a finding on its own.

## Authentication

Bypass, missing or inconsistent checks across entry points, weak session validation, fixation, reuse after logout, token validation flaws, algorithm confusion, missing expiry, insecure refresh handling, account enumeration, brute-force exposure, insecure recovery, wrong identity binding, trust in user-controlled identity claims, checks applied after sensitive actions. Verify the real flow, not route or middleware names.

## Authorization

Missing checks, direct object references, horizontal/vertical escalation, cross-tenant access, ownership confusion, role checks on the wrong identity, client-controlled privilege fields, UI-only enforcement, inconsistent read/write/update/delete coverage, unprotected background jobs and internal endpoints, check-to-use gaps. Per finding: attacker identity, required privilege, target, expected rule, enforcement location, reachability.

## Injection

Untrusted input reaching SQL, NoSQL, OS commands, shells, templates, expression languages, LDAP, XPath, GraphQL, regex, logs, headers, HTML/JS/CSS, deserialization, query builders, or search backends. Parameterized or encoded input counts only with bypass or unsafe-path evidence.

## Input validation

Missing or client-only validation, endpoint inconsistencies, type confusion, overflow, lossy coercion, null/undefined surprises, Unicode/normalization and canonicalization gaps, length/allowlist bypasses, validation before a semantics-changing transform, related-field gaps. Check syntax and semantics.

## File and path handling

Traversal, absolute-path and symlink bypasses, archive-extraction traversal, unsafe or predictable temp files, arbitrary read/write, permissions, user-controlled extensions, filename normalization, type confusion, upload-to-execution, local inclusion, unsafe cleanup. Trace input to filesystem call.

## Secrets and credentials

Hardcoded or committed secrets, secrets in logs/errors/URLs/client bundles, weak storage, credentials in fixtures, insecure defaults, secrets in images, unprotected env vars, unprotected transit. Separate real values from placeholders, test-only values, public identifiers, revoked credentials, and unverified candidates. Redact values.

## Cryptography

Broken/obsolete algorithms, hardcoded keys, predictable randomness, reused nonces, bad tag verification, missing integrity, weak password hashing or key derivation, exposed key material, broken cert validation, disabled TLS checks, encryption/encoding confusion, encryption without key management. Judge algorithm in its mode, parameters, and threat model.

## Data protection

Excessive exposure, sensitive data in logs, unencrypted sensitive storage, unprotected backups, missing deletion, cross-tenant leakage, misclassification, PII exposure, debug endpoints, sensitive telemetry, bad redaction, over-retention.

## Serialization and parsing

Unsafe deserialization, type confusion, prototype pollution, polymorphic-type abuse, object injection, parser differentials, entity expansion, resource exhaustion, signature bypass, untrusted data executed as instructions, cross-service serialization mismatch. Name parser, format, source, and dangerous sink.

## Dependencies

Validate manifest → lockfile → resolved version → advisory → affected range → actual usage → reachability → preconditions → mitigations. Never report on name match alone. Record package, resolved version, advisory id, affected/fixed versions, reachability, preconditions, direct vs. transitive, and limits. No advisory DB access = explicit limitation.

## Configuration and infrastructure

Insecure defaults, missing env validation, debug in exposed environments, broad permissions, exposed admin interfaces, missing network restrictions, insecure CORS, weak cookies, missing security headers, bad TLS, over-permissive IAM, unrestricted service accounts, missing resource limits, unsafe container settings, privileged execution, exposed internal ports, insecure temp storage. Separate dev settings from production config.

## Business logic

Workflow bypasses, missing state transitions, replays, duplicates, negative quantities, wrong limits, price/permission manipulation, races, bad approval flows, missing ownership checks, broken invariants, client-controlled security decisions, partial completion. State the expected invariant and the exact violation.

## Concurrency and resource safety

Races, check-to-use gaps, missing transaction boundaries, availability-killing deadlocks, unbounded queues/memory, leaks, blocking I/O on sensitive paths, missing timeouts, retry storms, unbounded recursion, regex DoS, repeated expensive ops. Theoretical races stay suspected until a realistic interleaving shows.

## Error handling and observability

Swallowed exceptions, fail-open behavior, missing error states, unsafe fallbacks, sensitive stack traces, credential/token logs, wrong status codes, retry-driven duplication, skipped cleanup, inconsistent handling across boundaries, undetectable security events.
