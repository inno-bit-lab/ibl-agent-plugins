---
doc_type: session-handoff
title: "<short title of the work>"
date: <ISO-8601, e.g. 2026-05-30T14:30:22Z>
repo: <repo name>
branch: <current branch>
base_sha: <short SHA the work sits on top of>
status: in-progress            # in-progress | blocked | ready-for-review
next_action: "<one imperative sentence naming the exact file/test/command>"
blockers: []                   # list, or [] if none
suggested_skills:
  - name: <plugin:skill>       # fully namespaced
    when: "<the moment / condition to invoke it>"
    why: "<what it does for the remaining work>"
    fallback: "<what to do if it is not available in the next session>"
key_files:
  - <path/to/file.ext>
verify: "<command that proves the next action is done>"
previous_handoff: <path or "none">
---

> **NEXT AGENT — read this first.** Parse the frontmatter, then run the **Verify
> first** block before changing anything. Start from `next_action`. Confirm each
> `suggested_skills[].name` is actually in your available skills; if one is
> missing, use its `fallback`. Treat this file as a snapshot that may be stale —
> trust the live repo/tests over this doc when they disagree.

# Handoff: <title>

## ▶ Next action
<Single imperative. Name the exact file/test/endpoint and the expected result.>
**Done when:** <objective pass/fail criterion>. **Verify with:** `<command>`.

## Verify first (reconcile with this doc before acting)
- `git status && git log --oneline -5` — branch + has HEAD moved past `base_sha`?
- `git stash list` — do the stashes named below still exist?
- `<build command>` — does it still compile?
- `<test command>` — do the pass/fail counts below still hold?
- Confirm required env vars / credentials are present (presence only).

## Goal
<One sentence: what we are building and its definition of done.>

## Current state  (freshness: ✅ verified / ⚠️ not re-run / ❓ assumed)
- **Working:** <what is confirmed green> [✅]
- **Broken / in progress:** <what is red and why> [⚠️]
- **Git:** branch `<x>` @ `<sha>`; staged: <...>; unstaged: <...>; stashes: <...>; untracked: <...>
- **Build / tests:** <status + exact commands + which tests fail and why>
- **Env / access:** <required vars/creds — present? presence only, never values>

## Work in flight  (intent, not diff — see `git diff <base_sha>`)
- `<path>` — <what was being done, how far it got> [✅/⚠️/❓]

## Failed approaches — DO NOT RETRY unless noted
- <approach> → <why it failed> → retry only if <condition changes>

## Key decisions this session  (link, don't restate)
| Decision | Why | Where the detail lives |
|---|---|---|
| <choice> | <because…> | <ADR/PR/issue path or URL> |

## Assumptions that could be wrong
- <assumption the next agent should challenge, not inherit>

## Suggested skills
Invoke in order; confirm each is available on your host first, then invoke it the
way your host invokes skills. Identify each by plugin + name (portable across hosts).

| Skill (plugin · name) | Why now (next action it serves) | When |
|---|---|---|
| `<plugin>` · `<skill>` | <ties to the remaining work> | <trigger / condition> |

Fallbacks if a skill is absent (or the next agent is on a host without it): <one line per skill>.

## Remaining work  (ordered backlog past the next action)
- [ ] <next bounded task>
- [ ] <after that>

## Open questions
- <question + who/what could answer it>

## Gotchas / do-not-touch
- <non-obvious trap; "looks broken but isn't"; "never X because Y">

## References  (pointers, not copies)
- PR: <url> · Issue: <url> · Plan/PRD: <path#section> · ADR: <path>
- Previous handoff: <path or "none">
