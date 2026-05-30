# The "Suggested skills" section

The handoff names which skills the next agent should invoke. Done well, this
section turns the remaining work into a sequence of skill-assisted actions.

**This skill is host-agnostic.** It runs under Claude Code, Codex, Antigravity,
and OpenCode. The *mechanics* of skill discovery and invocation differ per host,
so this section keeps the guidance portable: enumerate from whatever listing
your current host gives you, and write each suggestion so it survives the next
agent being on a different host — or having a different skill set.

## How to enumerate candidate skills

Read the skill/command listing your **current host** already exposes, and pick
the ones relevant to the remaining work — you rarely need to scan the
filesystem:

- **Claude Code / Agent SDK** — every skill's `name` + `description` is already
  in your context (the available-skills listing; "what skills are available?"
  surfaces it). Invoked via the Skill tool or `/<plugin>:<name>`.
- **Codex** — plugin skills installed from the marketplace
  (`.agents/plugins/marketplace.json`); list them with the host's plugin/skill
  command.
- **Antigravity** — plugins under `<workspace>/.agents/plugins/<plugin>/` or the
  global Gemini config plugins dir; surfaced in the agent's tool/skill list.
- **OpenCode** — individual skills under `<workspace>/.opencode/skills/<name>` or
  the global OpenCode skills dir.

If you need exact names/paths, the canonical source for IBL skills is this
marketplace repo (`plugins/<plugin>/skills/<name>/`); installed copies in each
host are generated from it (see the repo `AGENTS.md`).

## The caveat you MUST encode: skill sets are host- AND session-specific

The set the *next* agent sees can legitimately differ from yours — and the next
session may even run on a **different agent host**. Reasons: personal skills are
per-user and per-machine and don't sync across hosts/surfaces; plugin skills only
appear where that plugin is installed/enabled; project skills depend on the
launch directory; a host may hide or namespace skills differently; and some
hosts cap or truncate the listing. Never assume the next agent has the same
skills under the same names.

Therefore, make each suggestion **portable and self-describing**:

- Name the **source plugin + skill** (e.g. "the `ibl-abp` plugin's `abp-testing`
  skill"), not just a bare local alias — the next agent can map that to whatever
  its host calls it.
- Use your host's **invocation form** as a hint, and namespace where the host
  does (Claude Code/Codex use `plugin:skill`).
- Phrase each suggestion **conditionally**: "if available, invoke X; otherwise
  <fallback>".
- Pair each skill with a **one-line capability summary** so the next agent can
  act on intent even if the skill is absent, renamed, or on another host.
- Tell the next agent to **self-check** that the skill appears before invoking.

## Format: map skills to next actions, not a catalog

For each entry: **skill (plugin + name)**, **why now** (tie to the remaining
work), **when** (the trigger), and a **fallback**. Order to match the work
sequence.

```markdown
## Suggested skills
Invoke in order; confirm each is available on your host first, then invoke it the
way your host invokes skills. If one is missing, use its fallback. (Source of
truth: the `ibl-abp` plugin in the ibl-agent-plugins marketplace.)

| Skill (plugin · name)      | Why now (next action it serves)                    | When                         |
|----------------------------|----------------------------------------------------|------------------------------|
| `ibl-abp` · `abp-core`     | Baseline conventions; entry point for any ABP edit | Load first                   |
| `ibl-abp` · `abp-mongodb`  | The new Order aggregate needs its index + custom   | When wiring the repository   |
|                            | repository registered in the Mongo data context.   |                              |
| `ibl-abp` · `abp-testing`  | Next action is integration tests for OrderAppSvc;  | After it compiles, before PR |
|                            | owns the MongoSandbox + coverage conventions.      |                              |

Fallbacks if absent (or if the next agent is on a host without this skill):
- `abp-mongodb` → register the repo in `<Project>MongoDbContext` and add the
  index in `OnModelCreating` by hand.
- `abp-testing` → write xUnit integration tests against a MongoSandbox fixture.
```

Keep it to the **2–4 skills that serve the immediate next actions**. This
section sits in the TL;DR zone, so keep it terse; detail belongs lower in the
doc. Mirror the same essentials into the `suggested_skills` frontmatter list so
a parser (or the next session's handoff skill, on any host) can read them without
parsing prose.
