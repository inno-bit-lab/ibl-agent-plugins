---
name: agentic-orchestration
description: 'Use when planning, running, or resuming multi-agent work that needs model tiering, a fixed final reviewer, disjoint worker scopes, self-contained worker briefs, consolidation of outputs, declared autonomy, or post-dispatch sanity checks.'
---

# Agentic Orchestration

Use this skill when a task is large enough to benefit from several agents or
worker lanes, or when an existing multi-agent run needs to be resumed safely.
The purpose is to keep the work fast without losing accountability.

## Core Principle

Keep one orchestrator responsible for the final decision. The orchestrator may
delegate bounded work, but never delegates the final review, verdict, or merge
decision.

Use model capability as a risk control:

- Use the strongest available model for critical reasoning: architecture,
  security, adversarial review, ambiguous bugs, migration plans, and final
  consolidation.
- Use a capable implementation model for scoped code changes with clear
  verification commands.
- Use a cheaper or faster model only for bounded, low-risk work: reports,
  inventory, lint-like checks, documentation extraction, or duplicate searches.

Express tiers as capability and risk, not provider-specific model names. Hosts
and available models change; the decision rule should survive the host.

## When To Use

Use this skill when any of these are true:

- Two or more independent scopes can move in parallel.
- The user asks for an agentic strategy, subagents, worker lanes, or model
  tiering.
- A session resumes with agents, tasks, or scratch outputs already in flight.
- A previous dispatch produced unclear, empty, or conflicting results.
- The work needs a master consolidation file or review package before final
  action.

Do not use this skill to replace a host's native dispatching mechanics. Use the
host's available tools, but apply this orchestration discipline around them.

## Workflow

1. **State the target outcome.** Define the exact deliverable and the command or
   evidence that proves it is done.
2. **Partition into disjoint scopes.** Each worker gets files, modules, repos,
   or questions that do not overlap. If scopes overlap, serialize them or make
   one worker the owner.
3. **Assign capability by risk.** Match each lane to the lowest capability tier
   that is still safe for the task. Keep final consolidation on the strongest
   available reasoning tier.
4. **Write self-contained briefs.** Each worker brief must include objective,
   allowed paths, forbidden paths, source-of-truth docs, validation command,
   expected output file/comment, and stop conditions.
5. **Require durable outputs.** Workers must leave a file, patch, review note,
   log, or structured finding. Chat-only summaries are not enough for
   consolidation.
6. **Consolidate centrally.** The orchestrator reads the outputs, checks the
   diff, resolves conflicts, runs validation, and writes the final verdict.

## Worker Brief Template

```text
Objective:
Scope:
Do not touch:
Source of truth:
Expected output:
Validation:
Stop and report if:
```

For implementation workers, include the exact files or directories they may
edit. For review workers, include the exact diff, commit range, or artifact
paths they must inspect.

## Declared Autonomy

Before dispatching, state what workers may do without asking:

- allowed edits
- allowed commands
- network or service access boundaries
- whether they may create temporary files
- whether they may commit, push, or only report

Also state what blocks autonomy:

- ambiguous ownership
- failing validation outside the assigned scope
- missing credentials or environment
- destructive data operations
- overlap with another active worker's files

## Consolidation Checks

Before accepting worker output:

- run `git status` or the host equivalent and confirm files were actually
  touched when edits were expected
- inspect the output artifact; do not trust a success summary by itself
- compare worker claims against the diff or logs
- run the validation commands named in the brief
- record what was accepted, rejected, or needs another pass

For resume and known failure modes, read
`references/resume-and-failure-modes.md`.
