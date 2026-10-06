#!/usr/bin/env python3
"""
Workflow pre-hook: trigger the not-yet-migrated GitHub Actions workflows.

Transitional bridge. The praktika PR workflow is the single entry point approved
to run for PRs; from its Config job this hook dispatches the GH Actions workflows
that still own the unmigrated jobs (ci.yaml, codeql.yaml). Those workflows have
their `pull_request:` trigger commented out, so they no longer run on their own —
they run only when dispatched here. As each one's jobs finish migrating to
praktika, drop it from GH_WORKFLOWS (and eventually remove this hook).

Requirements:
  * The GitHub token minter must grant `actions: write` (workflow dispatch).
  * Each dispatched workflow must have a `workflow_dispatch:` trigger and exist on
    the default branch (GitHub requirement for dispatch).

Two refs are in play, and they are different things:

  * dispatch ref — which version of the workflow *definition* (its triggers,
    inputs, job steps) GitHub runs. The workflow_dispatch API reads the trigger +
    inputs from THIS ref's copy of the file, and only accepts a branch or tag.
  * pr_ref — `refs/pull/<N>/merge`, the PR's ephemeral merge commit (maintained
    in the base repo). Passed as an input so the workflows check it out and test
    the merged PR code.

Dispatch ref selection:
  * Same-repo PR → the PR's own head branch. Its files carry the pr_ref input and
    (for codeql) the workflow_dispatch trigger, so dispatch works even before the
    changes reach main. Safe: same-repo PR authors already have write access, so
    running their workflow definition is no escalation.
  * Fork PR → `main` (trusted definition), since a fork must not run its own
    workflow definition with our token. This requires the workflow changes to be
    on main; until then fork dispatch errors (expected during rollout).
"""
import subprocess
import sys

from praktika.info import Info
from praktika.gh_auth import GHAuth

# Each must have a `workflow_dispatch.inputs.pr_ref` and check it out.
GH_WORKFLOWS = ["ci.yaml", "codeql.yaml"]


def main() -> int:
    info = Info()
    if not info.pr_number or info.pr_number <= 0:
        print("Not a PR run; skipping GitHub Actions dispatch")
        return 0

    pr_ref = f"refs/pull/{info.pr_number}/merge"
    is_fork = bool(info.fork_name) and info.fork_name != info.repo_name
    dispatch_ref = "main" if is_fork else (info.git_branch or "main")
    repo = info.repo_name  # owner/repo; the ephemeral checkout has no git remote

    GHAuth.auth()  # mints + authenticates gh; needs actions:write on the minter

    rc = 0
    for wf in GH_WORKFLOWS:
        print(f"Dispatching {wf} on {dispatch_ref} with pr_ref={pr_ref}")
        if subprocess.run(
            ["gh", "workflow", "run", wf, "--repo", repo,
             "--ref", dispatch_ref, "-f", f"pr_ref={pr_ref}"]
        ).returncode != 0:
            print(f"ERROR: failed to dispatch {wf}")
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
