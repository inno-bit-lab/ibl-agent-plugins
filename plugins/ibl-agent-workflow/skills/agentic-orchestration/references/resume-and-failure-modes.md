# Resume Checklist And Failure Modes

Use this reference when continuing a multi-agent run or validating dispatch
results.

## Resume Checklist

Before launching or trusting more worker lanes:

- Run `git status --short --branch` and note the branch, upstream, staged,
  unstaged, and untracked files.
- Check whether any worker outputs, scratch files, review packages, or progress
  files already exist. Decide whether they are source evidence or disposable
  scratch.
- Identify tasks still in flight. If the host exposes task state, list active,
  completed, and failed tasks before dispatching more.
- Reconstruct the orchestrator role: which agent owns final review and which
  outputs still need consolidation.
- Confirm each active scope is disjoint. If two workers touched the same files,
  stop parallel work on those files and consolidate manually.
- Clean or archive obsolete scratch outputs only after confirming they are not
  the sole record of a worker's result.

## Required Output For Each Worker

Every worker lane should leave one durable output:

- code patch
- review note with file/line references
- structured findings file
- command log
- implementation summary tied to changed files
- explicit "no changes needed" note with evidence

If a worker reports success but leaves no output and was expected to edit or
write a file, treat the lane as failed until proven otherwise.

## Verified Failure Modes

### Degenerate Output

Symptom: a worker returns generic or repeated text that does not address the
brief.

Response:

- do not fold it into the final result
- tighten the brief to exact files, checks, and output format
- rerun with a stronger reasoning tier if the task was critical

### Zero Files Written

Symptom: a worker or pipeline claims completion, but `git status`, expected
artifact paths, or output directories show no files.

Response:

- check `git status` and expected output paths before accepting the result
- search for misplaced output under scratch/temp directories
- if no artifact exists, rerun or mark the lane failed

### Orphan Tasks

Symptom: tasks from an earlier session remain visible, running, or partially
complete, but the current orchestrator has no record of their scope.

Response:

- list active/completed/failed task state if the host exposes it
- reconcile each task with current branch and scratch outputs
- do not launch overlapping work until ownership is clear
- capture the final disposition in the consolidation note or handoff

## Master Consolidation File

For broad runs, keep one master file or PR comment with:

- lanes dispatched
- assigned scopes
- output paths
- validation status
- accepted findings or patches
- rejected/duplicate output
- final remaining risks

The master file is the handover point between parallel work and final review.
