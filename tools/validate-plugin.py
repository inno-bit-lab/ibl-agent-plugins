from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SKILLS = {
    "ibl-abp": {
        "abp-core",
        "abp-feature-dev",
        "abp-mongodb",
        "abp-multitenancy",
        "abp-react-ui",
        "abp-testing",
    },
    "ibl-skill-improvement": {
        "skill-improvement",
    },
}


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def ok(message: str) -> None:
    print(f"[OK] {message}")


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"{path.relative_to(ROOT)} is not valid JSON: {exc}")


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        fail(f"{path.relative_to(ROOT)} is missing YAML frontmatter")
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def validate_manifests() -> None:
    manifests = [
        ROOT / ".agents" / "plugins" / "marketplace.json",
        ROOT / ".claude-plugin" / "marketplace.json",
    ]
    for plugin_name in PLUGIN_SKILLS:
        plugin = ROOT / "plugins" / plugin_name
        manifests.extend([
            plugin / ".codex-plugin" / "plugin.json",
            plugin / ".claude-plugin" / "plugin.json",
            plugin / "plugin.json",
        ])
    for path in manifests:
        if not path.is_file():
            fail(f"missing manifest: {path.relative_to(ROOT)}")
        load_json(path)
        ok(f"valid JSON: {path.relative_to(ROOT)}")

    for plugin_name in PLUGIN_SKILLS:
        codex = load_json(ROOT / "plugins" / plugin_name / ".codex-plugin" / "plugin.json")
        if not isinstance(codex, dict):
            fail(f"{plugin_name} Codex plugin manifest root must be an object")
        if codex.get("name") != plugin_name:
            fail(f"{plugin_name} Codex plugin name mismatch")
        if codex.get("skills") != "./skills/":
            fail(f"{plugin_name} Codex plugin skills path must be ./skills/")
        prompts = codex.get("interface", {}).get("defaultPrompt")
        if not isinstance(prompts, list) or len(prompts) > 3:
            fail(f"{plugin_name} interface.defaultPrompt must be a list with at most 3 entries")


def validate_skills() -> None:
    for plugin_name, expected_skills in PLUGIN_SKILLS.items():
        skills = ROOT / "plugins" / plugin_name / "skills"
        if not skills.is_dir():
            fail(f"{plugin_name} missing skills directory")
        actual = {p.name for p in skills.iterdir() if p.is_dir()}
        missing = expected_skills - actual
        extra = actual - expected_skills
        if missing:
            fail(f"{plugin_name} missing expected skills: {', '.join(sorted(missing))}")
        if extra:
            warn(f"{plugin_name} unexpected skill directories: {', '.join(sorted(extra))}")

        for skill_name in sorted(expected_skills):
            skill_file = skills / skill_name / "SKILL.md"
            if not skill_file.is_file():
                fail(f"{plugin_name}/{skill_name} is missing SKILL.md")
            metadata = parse_frontmatter(skill_file)
            if metadata.get("name") != skill_name:
                fail(f"{plugin_name}/{skill_name} frontmatter name mismatch")
            description = metadata.get("description", "")
            if not description:
                fail(f"{plugin_name}/{skill_name} is missing description")
            if len(description) > 1024:
                fail(f"{plugin_name}/{skill_name} description is too long for Agent Skills: {len(description)} chars")
            ok(f"skill metadata: {plugin_name}/{skill_name}")


def validate_no_hardcoded_global_paths() -> None:
    offenders: list[str] = []
    patterns = ("~/.claude/skills", r"C:\Users\Innotech\.claude\skills")
    for path in (ROOT / "plugins").rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".py", ".json", ".txt", ".tmpl"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if pattern in text:
                offenders.append(str(path.relative_to(ROOT)))
                break
    if offenders:
        fail("hardcoded global skill paths found: " + ", ".join(offenders))
    ok("no hardcoded ~/.claude skill paths")


def validate_improvement_inbox() -> None:
    improvements = ROOT / "improvements"
    for dirname in ("inbox", "applied", "rejected", "_template"):
        if not (improvements / dirname).is_dir():
            fail(f"missing improvements/{dirname}/")
    for filename in ("problem.md", "improvement.md", "modified-resources.md", "validation.md"):
        path = improvements / "_template" / filename
        if not path.is_file():
            fail(f"missing improvements/_template/{filename}")
    ok("improvement inbox structure")


def main() -> int:
    validate_manifests()
    validate_skills()
    validate_no_hardcoded_global_paths()
    validate_improvement_inbox()
    ok("IBL agent plugin structure is complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
