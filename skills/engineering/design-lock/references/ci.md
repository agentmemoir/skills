# CI

`templates/design-lock.yml` runs on `pull_request_target` (opened, synchronize, reopened, labeled, unlabeled), `merge_group`, and pushes to main. Only the `design:approved-change` label reruns it. Other labels run nothing and cannot cancel a real run. Actions are pinned to commit SHAs.

GitHub runs the workflow and the tooling from the base branch. The pull request is checked out into `pr/` and measured with `base/tools/design-lock/designlock.py gate --root pr`, and `base/.../guard.py` runs the guard. The capture command builds and runs the PR's own code, so PR code does execute on the runner, with a read-only token and no secrets. Base tooling fails the gate if capture modified a frame, the config, the baseline, or a locked file, and it re-validates the measured output. A PR can still misreport its own rendering in the measured file, so a maintainer reviews the capture script (a locked path) and the report.

The guard rejects:

- a change to any protected path, or an added baseline entry, without both the label and a new ledger entry
- updated goldens or snapshots while the design check did not pass (a label never excuses this)

The first adoption PR (no config on the base) is left to a maintainer's review. A push drops the label, so an approval covers one commit. `design-ok` is the single required check. It fails unless both jobs succeeded (skipped counts as failure). Branch protection, the label permission, and the required check stay out of the agent's reach, for example behind a separate agent GitHub identity.
