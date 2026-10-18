// Integration layer: run each skill's own self-check and the repo's non-Node
// gates under the standard runner. Subtests are awaited one at a time, matching
// the previous `&&` chain, so stateful checks never overlap.

import { test } from "node:test";
import assert from "node:assert/strict";
import type { ExecFileOptions } from "node:child_process";
import { run } from "./helpers.mts";

const NODE: string = process.execPath;
const PY: string = "python3";

type Check = [label: string, cmd: string, args: string[], options?: ExecFileOptions];

const CHECKS: Check[] = [
  ["format --check", NODE, ["scripts/format.cjs", "--check"]],
  ["autopsy report", NODE, ["skills/quality/autopsy/scripts/generate-report.cjs", "--self-check"]],
  ["rust flake loop", "bash", ["skills/languages/rust-flaky-test-investigator/scripts/flake-loop.sh", "--self-check"]],
  ["python subprocess recipes", PY, ["skills/languages/python-subprocess-and-concurrency/scripts/verify-recipes.py"]],
  ["noexec python self-check", PY, ["skills/languages/noexec-python/scripts/self-check.py"]],
  ["noexec rust self-check", "bash", ["skills/languages/noexec-rust/scripts/self-check.sh"]],
  ["rust skill commands", NODE, ["scripts/verify-rust-skill-commands.cjs"]],
  ["humanizer vendored region", NODE, ["scripts/sync-humanizer.cjs"]],
  ["validate.sh", "bash", ["scripts/validate.sh", "--quick"]],
];

test("skill self-checks and repo gates pass", async (t): Promise<void> => {
  for (const [name, cmd, args, options] of CHECKS) {
    await t.test(name, async (): Promise<void> => {
      const result = await run(cmd, args, options);
      assert.equal(
        result.status,
        0,
        `${cmd} ${args.join(" ")} exited ${result.status}\n--- stdout ---\n${result.stdout}\n--- stderr ---\n${result.stderr}`,
      );
    });
  }
});
