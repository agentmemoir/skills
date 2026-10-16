# Tests

The suite runs on Node's built-in test runner (`node:test`) and is written in TypeScript that Node executes directly via **type stripping** — no `typescript` dependency, no build step, no transpile step. `.mts` means the files are ES modules even though the package is CommonJS.

Needs Node 22.18 or newer (see `engines` in `package.json`); CI runs it on Node 22 and 24.

```bash
npm test                                # everything: unit + repo + every skill self-check
node --test tests/repo.test.mts        # structural checks only
npm run test:autopsy                   # one skill's own self-check
tsc --noEmit                            # type-check (uses tsconfig.json + @types/node)
```

- `repo.test.mts` — structural invariants: skill names, marketplace, README, and `bin` targets.
- `skills.test.mts` — runs each skill's self-check and the repo gates, including `scripts/validate.sh`.

Type stripping only removes *erasable* syntax. Avoid `enum`, runtime `namespace`, parameter properties, import aliases, and decorators here; use `import type` for type-only imports. The CommonJS skill scripts are loaded from these ES modules with `createRequire` (`loadCjs` in `helpers.mts`).

`@types/node` is a dev dependency for the editor and `tsc`; it is not needed to *run* the tests.
