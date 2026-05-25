from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime
from pathlib import Path


REQUIRED_FILES = ("problem.md", "improvement.md", "modified-resources.md", "validation.md")
REQUIRED_DIRS = ("candidate", "attachments")


def find_repo_root(start: Path) -> Path:
    for parent in [start.resolve(), *start.resolve().parents]:
        if (parent / "plugins").is_dir() and (parent / "improvements").is_dir():
            return parent
    raise SystemExit("Could not find repo root containing plugins/ and improvements/.")


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:64] or "skill-improvement"


def write_if_missing(path: Path, text: str) -> None:
    if not path.exists():
        path.write_text(text, encoding="utf-8")


def new_artifact(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    inbox = root / "improvements" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = slugify(args.slug or args.problem or args.skill)
    artifact_id = f"{timestamp}-{slugify(args.agent)}-{slugify(args.skill)}-{slug}"
    artifact = inbox / artifact_id
    artifact.mkdir(parents=False, exist_ok=False)

    for dirname in REQUIRED_DIRS:
        (artifact / dirname).mkdir()
        write_if_missing(artifact / dirname / ".gitkeep", "\n")

    resources = "\n".join(f"- `{item}`" for item in args.resource)
    write_if_missing(
        artifact / "problem.md",
        f"""# Problem

## Affected Skill

- Skill: {args.skill}
- Plugin: {args.plugin}
- Agent/Host: {args.agent}

## What Happened

{args.problem}

## Expected Behavior


## Evidence

- Command/request:
- Error/output:
- Files involved:
""",
    )
    write_if_missing(
        artifact / "improvement.md",
        f"""# Improvement

## Proposed Change

{args.improvement}

## Rationale


## Scope


## Risks

""",
    )
    write_if_missing(
        artifact / "modified-resources.md",
        f"""# Modified Resources

{resources if resources else "- `plugins/<plugin>/skills/<skill>/SKILL.md`"}
""",
    )
    write_if_missing(
        artifact / "validation.md",
        """# Validation

## Checks Run

- [ ] Skill frontmatter validated
- [ ] Plugin manifest validated
- [ ] Relevant scripts compiled or tested
- [ ] Regression evidence added

## Commands

```powershell
python tools/validate-plugin.py
```

## Result

Pending.
""",
    )

    print(artifact.relative_to(root))
    return 0


def iter_artifacts(root: Path, state: str) -> list[Path]:
    base = root / "improvements" / state
    if not base.is_dir():
        return []
    return sorted([p for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")])


def list_artifacts(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    artifacts = iter_artifacts(root, args.state)
    if not artifacts:
        print(f"No artifacts in improvements/{args.state}.")
        return 0
    for artifact in artifacts:
        print(artifact.relative_to(root))
    return 0


def validate_artifact_path(root: Path, value: str) -> Path:
    path = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise SystemExit(f"Artifact path is outside repo root: {path}")
    if not path.is_dir():
        raise SystemExit(f"Artifact folder not found: {path}")
    return path


def validate_artifact(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    artifact = validate_artifact_path(root, args.artifact)
    errors: list[str] = []

    for filename in REQUIRED_FILES:
        path = artifact / filename
        if not path.is_file():
            errors.append(f"missing {filename}")
        elif not path.read_text(encoding="utf-8", errors="ignore").strip():
            errors.append(f"empty {filename}")

    for dirname in REQUIRED_DIRS:
        if not (artifact / dirname).is_dir():
            errors.append(f"missing {dirname}/")

    resources = artifact / "modified-resources.md"
    if resources.is_file():
        text = resources.read_text(encoding="utf-8", errors="ignore")
        paths = re.findall(r"`([^`]+)`", text)
        canonical = [p for p in paths if p.startswith("plugins/")]
        if not canonical:
            errors.append("modified-resources.md must list at least one plugins/... path")
        for rel in canonical:
            candidate = (root / rel).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                errors.append(f"resource escapes repo root: {rel}")

    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        return 1

    print(f"[OK] {artifact.relative_to(root)}")
    return 0


def move_artifact(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    artifact = validate_artifact_path(root, args.artifact)
    destination_base = root / "improvements" / args.state
    destination_base.mkdir(parents=True, exist_ok=True)
    destination = destination_base / artifact.name
    if destination.exists():
        raise SystemExit(f"Destination already exists: {destination.relative_to(root)}")
    shutil.move(str(artifact), str(destination))
    print(destination.relative_to(root))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and validate skill improvement inbox artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="Create an improvement artifact in improvements/inbox.")
    new.add_argument("--skill", required=True)
    new.add_argument("--plugin", required=True)
    new.add_argument("--agent", default="codex")
    new.add_argument("--problem", required=True)
    new.add_argument("--improvement", required=True)
    new.add_argument("--resource", action="append", default=[])
    new.add_argument("--slug")
    new.set_defaults(func=new_artifact)

    list_cmd = sub.add_parser("list", help="List artifacts.")
    list_cmd.add_argument("--state", choices=["inbox", "applied", "rejected"], default="inbox")
    list_cmd.set_defaults(func=list_artifacts)

    validate = sub.add_parser("validate", help="Validate one artifact folder.")
    validate.add_argument("artifact")
    validate.set_defaults(func=validate_artifact)

    move = sub.add_parser("move", help="Move an artifact to applied or rejected.")
    move.add_argument("artifact")
    move.add_argument("--state", choices=["applied", "rejected"], required=True)
    move.set_defaults(func=move_artifact)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
