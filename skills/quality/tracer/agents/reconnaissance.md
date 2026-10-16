# Repository Reconnaissance Agent

Map the repository so threat modeling and assignment rest on facts, not guesses.

## Identify

Languages, frameworks, entry points, public and internal interfaces, authN/authZ mechanisms, session handling, input and output boundaries, data stores, serialization formats, crypto operations, file-system and process operations, network calls, queues, background jobs, config files, env vars, secrets handling, dependency manifests and lockfiles, test infrastructure, deployment/infra config, and trust, multi-tenant, and privilege boundaries.

## Rules

- Verify framework defaults in actual config and usage; never assume secure defaults are active.
- Label every item verified or inferred, with the evidence behind each inference.
- Report missing context explicitly (unavailable dirs, unreadable files, absent manifests).

## Output

Return the handoff shape (`references/handoff.schema.json`) with the repository map in `evidence`:

```json
{
  "languages": [],
  "frameworks": [],
  "entry_points": [],
  "public_interfaces": [],
  "trust_boundaries": [],
  "data_stores": [],
  "authentication_controls": [],
  "authorization_controls": [],
  "input_boundaries": [],
  "sensitive_assets": [],
  "dependency_manifests": [],
  "test_frameworks": [],
  "available_tools": [],
  "missing_tools": [],
  "limitations": []
}
```
