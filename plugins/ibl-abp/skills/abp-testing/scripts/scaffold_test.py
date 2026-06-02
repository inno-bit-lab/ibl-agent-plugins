"""
scaffold_test.py — Generate an integration test skeleton for an ABP AppService.

Reads an existing I{Entity}AppService.cs (or accepts the entity name directly)
and emits a test file under the appropriate test project. The baseline CRUD
tests (list / get / create / update / delete / validation / filters) are always
included; lifecycle/multitenancy/bulk test blocks are emitted based on flags or
auto-detected from the AppService.

Usage:
    python scaffold_test.py --entity Book --plural Books
    python scaffold_test.py --entity-interface src/MyProject/Services/Books/IBookAppService.cs
    python scaffold_test.py            # interactive

Auto-detection:
    --include lifecycle    if the interface has `ChangeStatusAsync`
    --include multitenancy if the entity implements IMultiTenant
    --include bulk         if the interface has `DeleteByIdsAsync` or `DeleteAllAsync`

Explicit flags override the auto-detection: --include=lifecycle,bulk
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_ABP_CORE_SCRIPTS = str(Path(__file__).resolve().parents[2] / "abp-core" / "scripts")
if _ABP_CORE_SCRIPTS not in sys.path:
    sys.path.insert(0, _ABP_CORE_SCRIPTS)

from abp_context import (  # noqa: E402
    AbpContext,
    data_layer,
    load_or_prompt_config,
    resolve_artifact,
    resolve_placeholders,
    test_project_dir,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _is_layered(ctx: AbpContext) -> bool:
    return (ctx.template_type or "nolayers") in ("layered", "microservice")


def _data_infix(ctx: AbpContext) -> str:
    """The test-base infix matching the persistence provider: ABP names the
    bases {Project}MongoDbTestBase / {Project}EntityFrameworkCoreTestBase."""
    return "MongoDb" if (ctx.data_provider or "mongodb") == "mongodb" else "EntityFrameworkCore"


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        return input(f"{label}{suffix}: ").strip() or default
    except EOFError:
        return default


def _find_test_project(ctx: AbpContext) -> Path | None:
    sln = Path(ctx.solution_root) if ctx.solution_root else Path.cwd()
    test_bases = list(sln.rglob("*ApplicationTestBase.cs"))
    if test_bases:
        for tb in test_bases:
            if ".Application.Tests" in tb.as_posix():
                return tb.parent
        return test_bases[0].parent
    candidates = [p for p in sln.rglob("*.Tests") if p.is_dir()]
    return candidates[0] if candidates else None


def _derive_from_interface(path: Path) -> tuple[str, str, set[str]] | None:
    """
    Read I{Entity}AppService.cs and extract:
      - entity_name
      - feature plural (namespace last segment)
      - auto-detected feature set: {lifecycle, bulk}
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    m_iface = re.search(r"interface\s+I(\w+)AppService\b", text)
    m_ns = re.search(r"namespace\s+([\w\.]+)\s*[;{]", text)
    if not m_iface:
        return None
    entity = m_iface.group(1)
    if m_ns:
        plural = m_ns.group(1).rsplit(".", 1)[-1]
    else:
        plural = entity + "s"

    features: set[str] = set()
    if re.search(r"ChangeStatusAsync\s*\(", text):
        features.add("lifecycle")
    if re.search(r"DeleteByIdsAsync\s*\(|DeleteAllAsync\s*\(", text):
        features.add("bulk")
    return entity, plural, features


def _test_usings(ctx: AbpContext, plural: str) -> str:
    """The `using` lines a test needs to reach the entity, DTOs and AppService
    interface. Derived from the resolver, so layered (everything in the flat
    `Root.Plural` namespace → one using) and nolayers (three layer namespaces →
    three usings) both come out right without branching here."""
    namespaces: list[str] = []
    for kind in ("entity", "dto", "appservice_interface"):
        ns = resolve_artifact(ctx, kind, plural).namespace
        if ns and ns not in namespaces:
            namespaces.append(ns)
    return "\n".join(f"using {ns};" for ns in namespaces)


def _detect_test_base_class(ctx: AbpContext, test_dir: Path | None) -> str:
    """The base class for an AppService integration test.

    nolayers → {Project}ApplicationTestBase (single test project).
    layered  → the data-provider test base ({Project}MongoDbTestBase), because
               AppService integration tests need a real persistence provider and
               live in the *.MongoDB.Tests project. We prefer a base class that
               actually exists in the test project, falling back to the ABP
               naming convention."""
    project = ctx.project_name
    if not _is_layered(ctx):
        return f"{project}ApplicationTestBase"
    infix = _data_infix(ctx)
    if test_dir and test_dir.is_dir():
        for cs in test_dir.rglob(f"*{infix}TestBase.cs"):
            return cs.stem
    return f"{project}{infix}TestBase"


def _detect_multitenancy(sln_root: Path, entity: str) -> bool:
    for entity_file in sln_root.rglob(f"{entity}.cs"):
        if "obj" in entity_file.as_posix() or "Tests" in entity_file.as_posix():
            continue
        try:
            t = entity_file.read_text(encoding="utf-8", errors="ignore")
            if "IMultiTenant" in t:
                return True
        except OSError:
            continue
    return False


def _lifecycle_tests(entity: str, lower: str) -> str:
    return f"""[Fact]
    public async Task Should_Initialize_With_Default_State()
    {{
        // TODO: assert that a freshly created entity has the documented initial state.
    }}

    [Fact]
    public async Task Should_Change_Status_Through_Valid_Transition()
    {{
        // TODO: create entity in initial state, call ChangeStatusAsync with the
        // next allowed state, assert it succeeded and StatusChangedAt is set.
    }}

    [Fact]
    public async Task Should_Throw_On_Invalid_Status_Transition()
    {{
        // TODO: create entity, call ChangeStatusAsync with a forbidden state,
        // assert BusinessException with the InvalidStatusTransition code.
        var ex = await Should.ThrowAsync<BusinessException>(async () =>
        {{
            // await _{lower}AppService.ChangeStatusAsync(id, new Change{entity}StatusDto {{ NewStatus = ... }});
            await Task.CompletedTask;
        }});
        ex.Code.ShouldContain("InvalidStatusTransition");
    }}

    [Fact]
    public async Task Should_Be_Idempotent_When_Changing_Status_To_Same_Value()
    {{
        // TODO: ChangeStatusAsync to current status should not throw and should not
        // update StatusChangedAt twice.
    }}"""


def _multitenancy_tests(entity: str, lower: str) -> str:
    return f"""[Fact]
    public async Task Should_Isolate_{entity}_By_Tenant()
    {{
        var tenantA = Guid.NewGuid();
        var tenantB = Guid.NewGuid();

        using (CurrentTenant.Change(tenantA))
        {{
            await _{lower}AppService.CreateAsync(new CreateUpdate{entity}Dto
            {{
                // TODO: minimal valid input
            }});
        }}

        using (CurrentTenant.Change(tenantB))
        {{
            var listB = await _{lower}AppService.GetListAsync(new Get{entity}sInput());
            // Records created under tenantA must NOT appear in tenantB's list.
            // TODO: assert listB.TotalCount == 0 (or only B's own data).
        }}
    }}"""


def _bulk_tests(entity: str, lower: str) -> str:
    return f"""[Fact]
    public async Task Should_DeleteByIds_Many()
    {{
        // TODO: create N entities, collect their ids, call DeleteByIdsAsync,
        // assert the list is empty.
    }}

    [Fact]
    public async Task Should_DeleteAll_Matching_Filter()
    {{
        // TODO: create entities matching the filter and entities not matching it,
        // call DeleteAllAsync with the filter, assert only matching ones were deleted.
    }}"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold an integration test for an AppService")
    parser.add_argument("--entity", help="Entity name (e.g. Book)")
    parser.add_argument("--plural", help="Feature folder / namespace segment (e.g. Books)")
    parser.add_argument(
        "--entity-interface",
        help="Path to I{Entity}AppService.cs (derives entity+plural automatically)",
    )
    parser.add_argument(
        "--include",
        default="auto",
        help="Comma-separated test blocks to include: lifecycle, multitenancy, bulk. "
             "Default 'auto' = detect from the AppService/entity files.",
    )
    parser.add_argument("--output", help="Override output folder")
    parser.add_argument("--cwd", help="Override working directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing test file")
    args = parser.parse_args()

    ctx = load_or_prompt_config(args.cwd)
    entity = args.entity
    plural = args.plural
    detected_features: set[str] = set()

    if args.entity_interface:
        iface_path = Path(args.entity_interface)
        if not iface_path.is_file():
            print(f"Interface file not found: {iface_path}", file=sys.stderr)
            return 2
        derived = _derive_from_interface(iface_path)
        if derived:
            entity = entity or derived[0]
            plural = plural or derived[1]
            detected_features = derived[2]

    if not entity:
        entity = _prompt("Entity name (e.g. Book)")
    if not entity:
        print("Entity name required", file=sys.stderr)
        return 2
    if not plural:
        plural = _prompt("Plural / feature namespace segment", entity + "s")

    # Resolve --include
    sln_root = Path(ctx.solution_root) if ctx.solution_root else Path.cwd()
    if args.include == "auto":
        if _detect_multitenancy(sln_root, entity):
            detected_features.add("multitenancy")
        include = detected_features
    else:
        include = {x.strip().lower() for x in args.include.split(",") if x.strip()}

    if args.output:
        out_dir = Path(args.output)
        test_project = out_dir
    elif _is_layered(ctx):
        # AppService integration tests need a real persistence provider, so in a
        # layered solution they live in the *.MongoDB.Tests (or *.EntityFrameworkCore.Tests)
        # project rather than the abstract *.Application.Tests project.
        test_project = sln_root / test_project_dir(ctx, "data")
        out_dir = test_project / plural
    else:
        test_project = _find_test_project(ctx)
        if test_project is None:
            test_project = sln_root / "test"
            print(f"[warn] Could not locate test project; using {test_project}", file=sys.stderr)
        out_dir = test_project / plural

    out_file = out_dir / f"{entity}AppService_Tests.cs"
    if out_file.exists() and not args.force:
        print(f"[skip] {out_file} already exists (use --force to overwrite)")
        return 0

    template = (TEMPLATES_DIR / "AppServiceTest.cs.tmpl").read_text(encoding="utf-8")
    text = resolve_placeholders(template, ctx)

    lower = entity[0].lower() + entity[1:]
    test_base_class = _detect_test_base_class(ctx, test_project)
    test_usings = _test_usings(ctx, plural)
    text = (text
        .replace("{{ENTITY_NAME}}", entity)
        .replace("{{ENTITY_LOWER}}", lower)
        .replace("{{FEATURE_PLURAL}}", plural)
        .replace("{{TEST_USINGS}}", test_usings)
        .replace("{{TEST_BASE_CLASS}}", test_base_class)
        .replace("{{LIFECYCLE_TESTS}}",
                 _lifecycle_tests(entity, lower) if "lifecycle" in include else "")
        .replace("{{MULTITENANCY_TESTS}}",
                 _multitenancy_tests(entity, lower) if "multitenancy" in include else "")
        .replace("{{BULK_TESTS}}",
                 _bulk_tests(entity, lower) if "bulk" in include else "")
    )
    # Tidy: collapse any tripled blank lines created by empty substitutions
    text = re.sub(r"\n{3,}", "\n\n", text)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file.write_text(text, encoding="utf-8")
    print(f"[OK] Wrote {out_file}")
    print(f"     Included test blocks: {', '.join(sorted(include)) if include else '(none — baseline only)'}")
    print()
    print("Next steps:")
    print(f"  1. Fill in the TODO placeholders in {out_file.name}")
    print("  2. Add a data seeder if the list test needs pre-existing data")
    print(f"  3. dotnet test --filter {entity}AppService_Tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
