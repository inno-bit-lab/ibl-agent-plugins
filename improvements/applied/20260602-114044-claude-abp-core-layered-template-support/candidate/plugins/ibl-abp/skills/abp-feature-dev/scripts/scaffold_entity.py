"""
scaffold_entity.py — Generate an ABP feature folder (entity + DTOs + AppService
+ optional custom repository + optional bulk/excel/lookup endpoints + lifecycle
method + permission/mapper/localization snippets).

This script is **invoked after the conversational interview** documented in
the abp-feature-dev SKILL.md. It accepts every choice the interview captured
as a command-line flag, so the code that lands on disk reflects the user's
decisions on the first pass.

Run with no args to enter the script's own (terse) prompt mode — the
conversational interview led by Claude is preferred.

Examples:
    # Minimal — equivalent to the old behavior
    python scaffold_entity.py --name Book --plural Books \
        --properties "Name:string,Price:decimal,PublishedAt:DateTime?"

    # Full porting (Customer from Postgres)
    python scaffold_entity.py \
        --name Customer --plural Customers \
        --properties "LegalName:string,DisplayName:string,TaxId:string?@64,FiscalCode:string?@16..16,Address:string?@512,Country:string@2..2=IT,Segment:CustomerSegment,StatusChangedAt:DateTime?" \
        --enums "CustomerStatus:Prospect,Active,Churned;CustomerSegment:Smb,Enterprise,Public" \
        --audit Audited --multi-tenant yes \
        --filters "Filter:text(LegalName,DisplayName,TaxId);Status:enum;Segment:enum;Country:string" \
        --lifecycle "Status:Prospect->Active,Active->Churned" \
        --bulk-delete no --excel-export no --lookup no --custom-repository no

The output layout follows the detected solution template (abp_context.py).
The file→project mapping lives in ONE place — `resolve_artifact()` in
abp-core/scripts/abp_context.py — so both templates stay in sync.

  Single-project (nolayers / Simple Monolith — e.g. IBL360):
    {project}/Entities/{Plural}/            entity + enums
    {project}/Services/Dtos/{Plural}/       DTOs
    {project}/Services/{Plural}/            AppService + interface
    {project}/Data/{Plural}/                custom repository (if requested)
    {project}/{Project}DomainErrorCodes.cs  error codes (if lifecycle)

  Layered (DDD — separate projects, flat `Root.Plural` namespace):
    {Project}.Domain/{Plural}/                       entity, repo interface
    {Project}.Domain.Shared/{Plural}/                enums
    {Project}.Domain.Shared/{Project}DomainErrorCodes.cs
    {Project}.Application.Contracts/{Plural}/         DTOs + AppService interface
    {Project}.Application/{Plural}/                   AppService impl
    {Project}.MongoDB/MongoDb/{Plural}/               custom repository (if requested)

Review snippets (permissions/mapper/localization) are always written next to
the entity under `_review_artifacts/`, to be merged manually.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# --- abp_context import (shared with all abp-* skills) ---------------------
_ABP_CORE_SCRIPTS = str(Path(__file__).resolve().parents[2] / "abp-core" / "scripts")
if _ABP_CORE_SCRIPTS not in sys.path:
    sys.path.insert(0, _ABP_CORE_SCRIPTS)

from abp_context import (  # noqa: E402
    AbpContext,
    load_or_prompt_config,
    resolve_artifact,
)


# --- Constants -------------------------------------------------------------
VALUE_TYPES = {"int", "long", "decimal", "double", "float", "bool", "Guid", "DateTime"}
AUDIT_BASES = {
    "Entity": "AggregateRoot<Guid>",
    "Audited": "AuditedAggregateRoot<Guid>",
    "FullAudited": "FullAuditedAggregateRoot<Guid>",
}


# --- Data structures -------------------------------------------------------
@dataclass
class Prop:
    name: str
    type: str
    nullable: bool
    default: Optional[str] = None  # raw C# expression (e.g. "\"IT\"", "0", "Prospect")
    min_length: Optional[int] = None
    max_length: Optional[int] = None

    @property
    def cs_type(self) -> str:
        return f"{self.type}?" if self.nullable else self.type

    @property
    def is_value_type(self) -> bool:
        return self.type in VALUE_TYPES

    @property
    def is_enum(self) -> bool:
        # Enum if not a built-in type and not a string. Caller must keep
        # track of declared enums separately; this is a heuristic for the DTO.
        return not self.is_value_type and self.type not in {"string"}

    @property
    def needs_required_attr(self) -> bool:
        return self.type == "string" and not self.nullable

    @property
    def camel(self) -> str:
        return self.name[0].lower() + self.name[1:]


@dataclass
class EnumDecl:
    name: str
    values: list[str]


@dataclass
class FilterSpec:
    """One filter as captured from --filters."""
    name: str
    kind: str  # "text" | "string" | "enum" | "bool" | "dateRange" | "numRange" | "guid"
    args: list[str] = field(default_factory=list)  # extras (e.g. fields covered by text)
    enum_type: Optional[str] = None
    field_type: Optional[str] = None  # for numRange (int/decimal/...)


@dataclass
class LifecycleSpec:
    field: str
    enum_type: str
    transitions: list[tuple[str, str]]  # (from_value, to_value)
    initial: str  # default = first value of the enum
    timestamp_field: str = "StatusChangedAt"


@dataclass
class Options:
    audit: str = "Audited"               # Entity | Audited | FullAudited
    multi_tenant: bool = False
    concurrency: bool = False
    bulk_delete: bool = False
    excel_export: bool = False
    lookup: bool = False
    lookup_display: str = "DisplayName"
    custom_repository: bool = False
    split_create_update: bool = False
    public_setters: bool = False
    domain_event_on_create: bool = False
    no_app_service: bool = False


# --- Parsing helpers -------------------------------------------------------
_PROP_RE = re.compile(
    r"""^
        (?P<name>[A-Za-z_]\w*)
        \s*:\s*
        (?P<type>[A-Za-z_][\w.]*)
        (?P<nullable>\?)?
        (?:\s*@\s*(?P<len>\d+(?:\.\.\d+)?))?
        (?:\s*=\s*(?P<default>.+))?
    $""",
    re.VERBOSE,
)


def parse_properties(spec: str) -> list[Prop]:
    if not spec or not spec.strip():
        return []

    props: list[Prop] = []
    for chunk in _split_top_level(spec, ","):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = _PROP_RE.match(chunk)
        if not m:
            raise ValueError(f"Invalid property spec: {chunk!r}")
        name = m.group("name")
        ty = m.group("type")
        nullable = bool(m.group("nullable"))
        default = m.group("default").strip() if m.group("default") else None
        length = m.group("len")
        mn, mx = None, None
        if length:
            if ".." in length:
                a, b = length.split("..")
                mn, mx = int(a), int(b)
            else:
                mx = int(length)
        props.append(
            Prop(name=name, type=ty, nullable=nullable,
                 default=default, min_length=mn, max_length=mx)
        )
    return props


def parse_enums(spec: Optional[str]) -> list[EnumDecl]:
    if not spec:
        return []
    enums: list[EnumDecl] = []
    for chunk in spec.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise ValueError(f"Invalid enum spec: {chunk!r} (expected Name:V1,V2,...)")
        name, vals = chunk.split(":", 1)
        values = [v.strip() for v in vals.split(",") if v.strip()]
        if not values:
            raise ValueError(f"Enum {name!r} has no values")
        enums.append(EnumDecl(name=name.strip(), values=values))
    return enums


def parse_filters(spec: Optional[str], props: list[Prop],
                  enums: list[EnumDecl]) -> list[FilterSpec]:
    """
    --filters "Name:Kind[(args)];Name2:Kind2"
    """
    if not spec:
        return []
    enum_names = {e.name for e in enums}
    filters: list[FilterSpec] = []
    for chunk in spec.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = re.match(r"^(\w+):(\w+)(?:\(([^)]*)\))?$", chunk)
        if not m:
            raise ValueError(f"Invalid filter spec: {chunk!r}")
        name, kind = m.group(1), m.group(2)
        args = [a.strip() for a in (m.group(3) or "").split(",") if a.strip()]
        f = FilterSpec(name=name, kind=kind, args=args)
        # Resolve enum type for enum filters
        if kind == "enum":
            # The filter name should match a property of an enum type
            prop = next((p for p in props if p.name == name), None)
            if prop and prop.type in enum_names:
                f.enum_type = prop.type
            else:
                # The field may be lifecycle-injected (a `Status` enum is added by
                # --lifecycle, so it isn't in --properties). Resolve the enum type
                # by name convention against the declared enums — an enum named
                # {name}, *{name}, or one whose name contains {name}
                # (e.g. filter "Status" → enum "ProductStatus"). Only if nothing
                # matches do we fall back to the bare filter name, which would
                # otherwise emit a non-existent type like `public Status? Status`.
                match = next(
                    (e.name for e in enums
                     if e.name == name or e.name.endswith(name)
                     or name.lower() in e.name.lower()),
                    None,
                )
                f.enum_type = match or name
        if kind == "numRange":
            prop = next((p for p in props if p.name == name), None)
            if prop:
                f.field_type = prop.type
            else:
                f.field_type = "decimal"
        filters.append(f)
    return filters


def parse_lifecycle(spec: Optional[str], enums: list[EnumDecl]) -> Optional[LifecycleSpec]:
    """
    --lifecycle "Status:Prospect->Active,Active->Churned"
    The enum for `Status` is found in `enums` (a property named Status with an
    enum type, or an enum named {Entity}Status).
    """
    if not spec:
        return None
    if ":" not in spec:
        raise ValueError(f"Invalid lifecycle spec: {spec!r}")
    field, transitions_str = spec.split(":", 1)
    field = field.strip()
    transitions: list[tuple[str, str]] = []
    for arrow in transitions_str.split(","):
        arrow = arrow.strip()
        if "->" not in arrow:
            raise ValueError(f"Invalid transition: {arrow!r}")
        a, b = (s.strip() for s in arrow.split("->", 1))
        transitions.append((a, b))

    # Resolve the enum type by name convention or first-match
    enum_type = None
    for e in enums:
        if e.name.endswith(field) or e.name == field or field.lower() in e.name.lower():
            enum_type = e.name
            break
    if enum_type is None and enums:
        enum_type = enums[0].name  # last-resort fallback

    if enum_type is None:
        raise ValueError(
            f"Lifecycle references field {field!r} but no enum was declared. "
            "Pass --enums for the corresponding enum."
        )

    initial = transitions[0][0] if transitions else "Unknown"
    return LifecycleSpec(field=field, enum_type=enum_type,
                         transitions=transitions, initial=initial)


def _split_top_level(s: str, sep: str) -> list[str]:
    """Split by sep ignoring separators inside (parens or brackets)."""
    out: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in s:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


# --- C# code builders ------------------------------------------------------
def cs_enum(decl: EnumDecl, ns: str) -> str:
    body = ",\n    ".join(decl.values)
    return f"""namespace {ns};

public enum {decl.name}
{{
    {body}
}}
"""


def cs_domain_error_codes(root_ns: str, plural: str, codes: list[str]) -> str:
    """
    Generate (or augment) Ibl360DomainErrorCodes.cs. Caller decides whether
    to write fresh or merge.
    """
    if not codes:
        return ""
    body = "\n".join(
        f'        public const string {c} = "{root_ns}:{plural}:{c}";'
        for c in codes
    )
    return f"""namespace {root_ns};

public static class {root_ns}DomainErrorCodes
{{
    public static class {plural}
    {{
{body}
    }}
}}
"""


def cs_entity(entity: str, plural: str, ns: str, root_ns: str,
              props: list[Prop], enums: list[EnumDecl],
              opts: Options, lifecycle: Optional[LifecycleSpec]) -> str:
    """Build the Customer.cs (or equivalent) source."""
    base = AUDIT_BASES[opts.audit]
    bases: list[str] = [base]
    if opts.multi_tenant:
        bases.append("IMultiTenant")
    if opts.concurrency:
        bases.append("IHasConcurrencyStamp")

    bases_str = ", ".join(bases)

    set_kw = "set" if opts.public_setters else "private set"

    # Build properties (private setters for rich; public for trivial)
    prop_lines: list[str] = []
    if opts.multi_tenant:
        prop_lines.append("    public Guid? TenantId { get; set; }")
        prop_lines.append("")
    if opts.concurrency:
        prop_lines.append("    public string ConcurrencyStamp { get; set; } = default!;")
        prop_lines.append("")

    enum_names = {e.name for e in enums}
    for p in props:
        default = ""
        if p.default is not None:
            default = f" = {p.default};"
        elif p.type == "string" and not p.nullable:
            default = " = default!;"
        prop_lines.append(f"    public {p.cs_type} {p.name} {{ get; {set_kw}; }}{default}")

    if lifecycle:
        # Inject Status + StatusChangedAt at the end (idempotent — they're already
        # in the property list if the user passed them explicitly)
        existing = {p.name for p in props}
        if lifecycle.field not in existing:
            prop_lines.append(
                f"    public {lifecycle.enum_type} {lifecycle.field} "
                f"{{ get; {set_kw}; }}"
            )
        if lifecycle.timestamp_field not in existing:
            prop_lines.append(
                f"    public DateTime? {lifecycle.timestamp_field} "
                f"{{ get; {set_kw}; }}"
            )

    prop_block = "\n".join(prop_lines)

    # --- Constructor parameter ordering ---------------------------------
    # C# requires non-defaulted parameters BEFORE defaulted ones, otherwise
    # the compiler errors out. We partition props into two groups and emit
    # required first, then optional. This same ordering is exposed via
    # `ordered_ctor_args` so the AppService Create call matches.
    ctor_props = [p for p in props
                  if not (lifecycle and p.name in (lifecycle.field, lifecycle.timestamp_field))]
    required_props = [p for p in ctor_props if not (p.nullable or p.default is not None)]
    optional_props = [p for p in ctor_props if (p.nullable or p.default is not None)]
    ordered_props = required_props + optional_props

    def _param(p: Prop) -> str:
        s = f"{p.cs_type} {p.camel}"
        if p.nullable or p.default is not None:
            default = p.default if p.default is not None else "null"
            s += f" = {default}"
        return s

    def _assign(p: Prop) -> str:
        if p.type == "string" and not p.nullable:
            if p.max_length:
                return (f"        {p.name} = Check.NotNullOrWhiteSpace({p.camel}, "
                        f"nameof({p.camel}), maxLength: {p.max_length});")
            return (f"        {p.name} = Check.NotNullOrWhiteSpace({p.camel}, "
                    f"nameof({p.camel}));")
        if p.type == "string" and p.nullable and p.max_length:
            return (f"        {p.name} = string.IsNullOrWhiteSpace({p.camel}) "
                    f"? null : {p.camel}.Trim();")
        return f"        {p.name} = {p.camel};"

    ctor_params = [_param(p) for p in ordered_props]
    ctor_assigns = [_assign(p) for p in ordered_props]

    if lifecycle:
        ctor_assigns.append(f"        {lifecycle.field} = {lifecycle.enum_type}.{lifecycle.initial};")
        ctor_assigns.append(f"        {lifecycle.timestamp_field} = null;")

    ctor_params_str = ",\n        ".join(["Guid id"] + ctor_params)

    # Build the Update(...) method — same params as ctor minus lifecycle
    update_params_str = ",\n        ".join(ctor_params) if ctor_params else ""
    update_assigns: list[str] = [_assign(p) for p in ordered_props]

    update_method = ""
    if update_params_str and not opts.public_setters:
        update_method = f"""
    public void Update(
        {update_params_str})
    {{
{chr(10).join(update_assigns)}
    }}
"""

    # Build ChangeStatus method if lifecycle present
    change_status_method = ""
    if lifecycle:
        switch_arms = "\n            ".join(
            f"({lifecycle.enum_type}.{a}, {lifecycle.enum_type}.{b}) => true,"
            for a, b in lifecycle.transitions
        )
        change_status_method = f"""
    public void ChangeStatus({lifecycle.enum_type} newStatus, IClock clock)
    {{
        Check.NotNull(clock, nameof(clock));

        if (newStatus == {lifecycle.field})
        {{
            return;
        }}

        if (!IsValidTransition({lifecycle.field}, newStatus))
        {{
            throw new BusinessException(
                {root_ns}DomainErrorCodes.{plural}.InvalidStatusTransition)
                .WithData("From", {lifecycle.field})
                .WithData("To", newStatus);
        }}

        {lifecycle.field} = newStatus;
        {lifecycle.timestamp_field} = clock.Now;
    }}

    private static bool IsValidTransition({lifecycle.enum_type} from, {lifecycle.enum_type} to)
    {{
        return (from, to) switch
        {{
            {switch_arms}
            _ => false
        }};
    }}
"""

    usings = [
        "using System;",
        "using Volo.Abp;",
        f"using Volo.Abp.Domain.Entities.Auditing;",
    ]
    if opts.multi_tenant:
        usings.append("using Volo.Abp.MultiTenancy;")
    if opts.concurrency:
        usings.append("using Volo.Abp.Domain.Entities;")
    if lifecycle:
        usings.append("using Volo.Abp.Timing;")

    using_block = "\n".join(sorted(set(usings)))

    body = f"""{using_block}

namespace {ns};

public class {entity} : {bases_str}
{{
{prop_block}

    protected {entity}() {{ }}

    public {entity}(
        {ctor_params_str}) : base(id)
    {{
{chr(10).join(ctor_assigns)}
    }}
{update_method}{change_status_method}}}
"""
    return body


def cs_dto(entity: str, ns: str, props: list[Prop], opts: Options,
           lifecycle: Optional[LifecycleSpec], dtos_ns: str,
           enums_ns: str) -> str:
    base = "AuditedEntityDto<Guid>" if opts.audit != "Entity" else "EntityDto<Guid>"
    if opts.audit == "FullAudited":
        base = "FullAuditedEntityDto<Guid>"
    lines: list[str] = []
    if opts.multi_tenant:
        lines.append("    public Guid? TenantId { get; set; }")
    if opts.concurrency:
        lines.append("    public string ConcurrencyStamp { get; set; } = default!;")
    for p in props:
        default = ""
        if p.default is not None:
            default = f" = {p.default};"
        elif p.type == "string" and not p.nullable:
            default = " = default!;"
        lines.append(f"    public {p.cs_type} {p.name} {{ get; set; }}{default}")
    if lifecycle:
        existing = {p.name for p in props}
        if lifecycle.field not in existing:
            lines.append(f"    public {lifecycle.enum_type} {lifecycle.field} {{ get; set; }}")
        if lifecycle.timestamp_field not in existing:
            lines.append(f"    public DateTime? {lifecycle.timestamp_field} {{ get; set; }}")
    body = "\n".join(lines)

    return f"""using System;
using {enums_ns};
using Volo.Abp.Application.Dtos;

namespace {dtos_ns};

public class {entity}Dto : {base}
{{
{body}
}}
"""


def cs_create_update_dto(entity: str, dtos_ns: str, enums_ns: str,
                         props: list[Prop], opts: Options) -> str:
    annotations = []
    for p in props:
        attrs: list[str] = []
        if p.needs_required_attr:
            attrs.append("[Required]")
        if p.type == "string":
            if p.min_length and p.max_length:
                attrs.append(f"[StringLength({p.max_length}, MinimumLength = {p.min_length})]")
            elif p.max_length:
                attrs.append(f"[StringLength({p.max_length})]")
        default = ""
        if p.default is not None:
            default = f" = {p.default};"
        elif p.type == "string" and not p.nullable:
            default = " = string.Empty;"
        line = f"    public {p.cs_type} {p.name} {{ get; set; }}{default}"
        annotations.extend([f"    {a}" for a in attrs])
        annotations.append(line)
        annotations.append("")

    body = "\n".join(annotations).rstrip()

    concurrency_line = ""
    if opts.concurrency:
        concurrency_line = "\n    [Required]\n    public string ConcurrencyStamp { get; set; } = default!;"

    return f"""using System;
using System.ComponentModel.DataAnnotations;
using {enums_ns};

namespace {dtos_ns};

public class CreateUpdate{entity}Dto
{{
{body}{concurrency_line}
}}
"""


def cs_get_input(plural: str, dtos_ns: str, enums_ns: str,
                 filters: list[FilterSpec]) -> str:
    field_lines: list[str] = []
    for f in filters:
        if f.kind in ("text", "string"):
            field_lines.append(f"    public string? {f.name} {{ get; set; }}")
        elif f.kind == "enum":
            et = f.enum_type or f.name
            field_lines.append(f"    public {et}? {f.name} {{ get; set; }}")
        elif f.kind == "bool":
            field_lines.append(f"    public bool? {f.name} {{ get; set; }}")
        elif f.kind == "dateRange":
            field_lines.append(f"    public DateTime? {f.name}From {{ get; set; }}")
            field_lines.append(f"    public DateTime? {f.name}To {{ get; set; }}")
        elif f.kind == "numRange":
            t = f.field_type or "decimal"
            field_lines.append(f"    public {t}? {f.name}Min {{ get; set; }}")
            field_lines.append(f"    public {t}? {f.name}Max {{ get; set; }}")
        elif f.kind == "guid":
            field_lines.append(f"    public Guid? {f.name} {{ get; set; }}")

    body = "\n".join(field_lines) if field_lines else "    // No filters declared"
    return f"""using System;
using {enums_ns};
using Volo.Abp.Application.Dtos;

namespace {dtos_ns};

public class Get{plural}Input : PagedAndSortedResultRequestDto
{{
{body}
}}
"""


def cs_change_status_dto(entity: str, dtos_ns: str, enums_ns: str,
                         lifecycle: LifecycleSpec) -> str:
    return f"""using System.ComponentModel.DataAnnotations;
using {enums_ns};

namespace {dtos_ns};

public class Change{entity}StatusDto
{{
    [Required]
    public {lifecycle.enum_type} NewStatus {{ get; set; }}
}}
"""


def cs_lookup_dto(entity: str, dtos_ns: str) -> str:
    return f"""using System;
using Volo.Abp.Application.Dtos;

namespace {dtos_ns};

public class {entity}LookupDto
{{
    public Guid Id {{ get; set; }}
    public string DisplayName {{ get; set; }} = default!;
}}

public class {entity}LookupRequestDto : PagedAndSortedResultRequestDto
{{
    public string? Filter {{ get; set; }}
}}
"""


def cs_excel_dto(entity: str, dtos_ns: str, props: list[Prop]) -> str:
    lines: list[str] = []
    for p in props:
        # Only include simple types in the export — skip nested types
        if p.is_enum:
            lines.append(f"    public string {p.name} {{ get; set; }} = default!;")
        elif p.type == "string":
            lines.append(f"    public {p.cs_type} {p.name} {{ get; set; }}{' = default!;' if not p.nullable else ''}")
        else:
            lines.append(f"    public {p.cs_type} {p.name} {{ get; set; }}")
    lines.append("    public DateTime CreationTime { get; set; }")
    body = "\n".join(lines)
    return f"""using System;

namespace {dtos_ns};

public class {entity}ExcelDto
{{
{body}
}}

public class {entity}ExcelDownloadDto : Get{entity}sInput
{{
    public string DownloadToken {{ get; set; }} = default!;
}}

public class {entity}DownloadTokenCacheItem
{{
    public string Token {{ get; set; }} = default!;
}}
"""


def cs_app_service_interface(entity: str, plural: str, services_ns: str,
                             dtos_ns: str, opts: Options,
                             lifecycle: Optional[LifecycleSpec]) -> str:
    extra: list[str] = []
    if lifecycle:
        extra.append(f"    Task<{entity}Dto> ChangeStatusAsync(Guid id, Change{entity}StatusDto input);")
    if opts.bulk_delete:
        extra.append("    Task DeleteByIdsAsync(List<Guid> ids);")
        extra.append(f"    Task DeleteAllAsync(Get{plural}Input input);")
    if opts.excel_export:
        extra.append(f"    Task<IRemoteStreamContent> GetListAsExcelFileAsync({entity}ExcelDownloadDto input);")
        extra.append("    Task<DownloadTokenResultDto> GetDownloadTokenAsync();")
    if opts.lookup:
        extra.append(f"    Task<PagedResultDto<{entity}LookupDto>> GetLookupAsync({entity}LookupRequestDto input);")

    extra_block = "\n" + "\n".join(extra) if extra else ""

    usings = [
        "using System;",
        "using System.Collections.Generic;",
        "using System.Threading.Tasks;",
        f"using {dtos_ns};",
        "using Volo.Abp.Application.Dtos;",
        "using Volo.Abp.Application.Services;",
    ]
    if opts.excel_export:
        usings.append("using Volo.Abp.Content;")
    using_block = "\n".join(sorted(set(usings)))

    return f"""{using_block}

namespace {services_ns};

public interface I{entity}AppService :
    ICrudAppService<
        {entity}Dto,
        Guid,
        Get{plural}Input,
        CreateUpdate{entity}Dto>
{{{extra_block}
}}
"""


def cs_app_service(entity: str, plural: str, root_ns: str, project_ns: str,
                   services_ns: str, dtos_ns: str, entities_ns: str,
                   props: list[Prop], filters: list[FilterSpec],
                   opts: Options, lifecycle: Optional[LifecycleSpec]) -> str:
    # Build filter application LINQ
    filter_lines: list[str] = []
    for f in filters:
        if f.kind == "text":
            # Case-insensitive substring search: both sides lowercased.
            # MongoDB LINQ translates ToLower() to $toLower (single round-trip);
            # EF Core translates to LOWER(field). Same code, works on both.
            # See abp-feature-dev/references/filter-design.md, "Case-insensitive
            # text search" for the rationale and performance notes.
            fields = f.args or [p.name for p in props if p.type == "string"][:3]
            or_chain = " ||\n                ".join(
                f'c.{fld} != null && c.{fld}.ToLower().Contains(__filter)' if any(
                    p.name == fld and p.nullable for p in props
                ) else f"c.{fld}.ToLower().Contains(__filter)"
                for fld in fields
            )
            filter_lines.append(f"""
        if (!string.IsNullOrWhiteSpace(input.{f.name}))
        {{
            var __filter = input.{f.name}.Trim().ToLowerInvariant();
            queryable = queryable.Where(c =>
                {or_chain});
        }}""")
        elif f.kind == "string":
            # Case-insensitive exact match. Same rationale as the text filter
            # above — compare lowercased on both sides.
            filter_lines.append(f"""
        if (!string.IsNullOrWhiteSpace(input.{f.name}))
        {{
            var __v = input.{f.name}.Trim().ToLowerInvariant();
            queryable = queryable.Where(c => c.{f.name}.ToLower() == __v);
        }}""")
        elif f.kind == "enum":
            filter_lines.append(f"""
        if (input.{f.name}.HasValue)
        {{
            queryable = queryable.Where(c => c.{f.name} == input.{f.name}.Value);
        }}""")
        elif f.kind == "bool":
            filter_lines.append(f"""
        if (input.{f.name}.HasValue)
        {{
            queryable = queryable.Where(c => c.{f.name} == input.{f.name}.Value);
        }}""")
        elif f.kind == "dateRange":
            filter_lines.append(f"""
        if (input.{f.name}From.HasValue)
        {{
            queryable = queryable.Where(c => c.{f.name} >= input.{f.name}From.Value);
        }}
        if (input.{f.name}To.HasValue)
        {{
            queryable = queryable.Where(c => c.{f.name} <= input.{f.name}To.Value);
        }}""")
        elif f.kind == "numRange":
            filter_lines.append(f"""
        if (input.{f.name}Min.HasValue)
        {{
            queryable = queryable.Where(c => c.{f.name} >= input.{f.name}Min.Value);
        }}
        if (input.{f.name}Max.HasValue)
        {{
            queryable = queryable.Where(c => c.{f.name} <= input.{f.name}Max.Value);
        }}""")
        elif f.kind == "guid":
            filter_lines.append(f"""
        if (input.{f.name}.HasValue)
        {{
            queryable = queryable.Where(c => c.{f.name} == input.{f.name}.Value);
        }}""")

    filter_block = "".join(filter_lines)
    default_sort_field = props[0].name if props else "Id"

    # ctor args used by Create — must mirror the entity's ctor parameter order
    # (required props first, then optional props with defaults). Same applies
    # to the Update(...) method.
    _ctor_props = [p for p in props
                   if not (lifecycle and p.name in (lifecycle.field, lifecycle.timestamp_field))]
    _required = [p for p in _ctor_props if not (p.nullable or p.default is not None)]
    _optional = [p for p in _ctor_props if (p.nullable or p.default is not None)]
    ctor_args = ", ".join(f"input.{p.name}" for p in (_required + _optional))
    update_args = ctor_args  # same shape

    # Optional methods
    optional_methods = ""

    if lifecycle:
        optional_methods += f"""
    [Authorize({root_ns}Permissions.{plural}.Edit)]
    public async Task<{entity}Dto> ChangeStatusAsync(Guid id, Change{entity}StatusDto input)
    {{
        var entity = await _repository.GetAsync(id);
        entity.ChangeStatus(input.NewStatus, Clock);
        await _repository.UpdateAsync(entity);
        return ObjectMapper.Map<{entity}, {entity}Dto>(entity);
    }}
"""

    if opts.bulk_delete:
        optional_methods += f"""
    [Authorize({root_ns}Permissions.{plural}.Delete)]
    public async Task DeleteByIdsAsync(List<Guid> ids)
    {{
        await _repository.DeleteManyAsync(ids);
    }}

    [Authorize({root_ns}Permissions.{plural}.Delete)]
    public async Task DeleteAllAsync(Get{plural}Input input)
    {{
        var queryable = await _repository.GetQueryableAsync();
        queryable = ApplyFilter(queryable, input);
        var ids = await AsyncExecuter.ToListAsync(queryable.Select(c => c.Id));
        await _repository.DeleteManyAsync(ids);
    }}
"""

    if opts.lookup:
        optional_methods += f"""
    public async Task<PagedResultDto<{entity}LookupDto>> GetLookupAsync({entity}LookupRequestDto input)
    {{
        var queryable = await _repository.GetQueryableAsync();
        if (!string.IsNullOrWhiteSpace(input.Filter))
        {{
            // Case-insensitive substring search — both sides lowercased.
            var __filter = input.Filter.Trim().ToLowerInvariant();
            queryable = queryable.Where(c => c.{opts.lookup_display}.ToLower().Contains(__filter));
        }}
        var totalCount = await AsyncExecuter.CountAsync(queryable);
        var query = queryable
            .OrderBy(input.Sorting.IsNullOrWhiteSpace() ? nameof({entity}.{opts.lookup_display}) : input.Sorting)
            .Skip(input.SkipCount)
            .Take(input.MaxResultCount)
            .Select(c => new {entity}LookupDto {{ Id = c.Id, DisplayName = c.{opts.lookup_display} }});
        var items = await AsyncExecuter.ToListAsync(query);
        return new PagedResultDto<{entity}LookupDto>(totalCount, items);
    }}
"""

    excel_block = ""
    excel_ctor_field = ""
    excel_ctor_param = ""
    excel_ctor_assign = ""
    if opts.excel_export:
        excel_ctor_field = (
            f"\n    private readonly IDistributedCache<{entity}DownloadTokenCacheItem, string> _downloadTokenCache;"
        )
        excel_ctor_param = (
            f",\n        IDistributedCache<{entity}DownloadTokenCacheItem, string> downloadTokenCache"
        )
        excel_ctor_assign = "\n        _downloadTokenCache = downloadTokenCache;"
        excel_block = f"""
    public async Task<DownloadTokenResultDto> GetDownloadTokenAsync()
    {{
        var token = Guid.NewGuid().ToString("N");
        await _downloadTokenCache.SetAsync(token,
            new {entity}DownloadTokenCacheItem {{ Token = token }},
            new DistributedCacheEntryOptions
            {{
                AbsoluteExpirationRelativeToNow = TimeSpan.FromSeconds(30)
            }});
        return new DownloadTokenResultDto {{ Token = token }};
    }}

    [AllowAnonymous]
    public async Task<IRemoteStreamContent> GetListAsExcelFileAsync({entity}ExcelDownloadDto input)
    {{
        var cached = await _downloadTokenCache.GetAsync(input.DownloadToken);
        if (cached == null || cached.Token != input.DownloadToken)
        {{
            throw new AbpAuthorizationException("Invalid download token: " + input.DownloadToken);
        }}

        var queryable = await _repository.GetQueryableAsync();
        queryable = ApplyFilter(queryable, input);
        var items = await AsyncExecuter.ToListAsync(queryable);

        var stream = new MemoryStream();
        await stream.SaveAsAsync(ObjectMapper.Map<List<{entity}>, List<{entity}ExcelDto>>(items));
        stream.Position = 0;
        return new RemoteStreamContent(stream, "{plural}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    }}
"""

    # ApplyFilter method (private) used by bulk-delete + excel
    apply_filter_method = ""
    if opts.bulk_delete or opts.excel_export:
        apply_filter_method = f"""
    private IQueryable<{entity}> ApplyFilter(IQueryable<{entity}> queryable, Get{plural}Input input)
    {{
{filter_block}
        return queryable;
    }}
"""

    usings = [
        "using System;",
        "using System.Collections.Generic;",
        "using System.Linq;",
        "using System.Linq.Dynamic.Core;",
        "using System.Threading.Tasks;",
        f"using {entities_ns};",
        f"using {dtos_ns};",
        f"using {root_ns}.Permissions;",
        "using Microsoft.AspNetCore.Authorization;",
        "using Volo.Abp.Application.Dtos;",
        "using Volo.Abp.Application.Services;",
        "using Volo.Abp.Domain.Repositories;",
    ]
    if opts.excel_export:
        usings += [
            "using System.IO;",
            "using Microsoft.Extensions.Caching.Distributed;",
            "using MiniExcelLibs;",
            "using Volo.Abp;",
            "using Volo.Abp.Authorization;",
            "using Volo.Abp.Caching;",
            "using Volo.Abp.Content;",
        ]
    using_block = "\n".join(sorted(set(usings)))

    return f"""{using_block}

namespace {services_ns};

[Authorize({root_ns}Permissions.{plural}.Default)]
public class {entity}AppService : ApplicationService, I{entity}AppService
{{
    private readonly IRepository<{entity}, Guid> _repository;{excel_ctor_field}

    public {entity}AppService(
        IRepository<{entity}, Guid> repository{excel_ctor_param})
    {{
        _repository = repository;{excel_ctor_assign}
    }}

    public async Task<{entity}Dto> GetAsync(Guid id)
    {{
        var entity = await _repository.GetAsync(id);
        return ObjectMapper.Map<{entity}, {entity}Dto>(entity);
    }}

    public async Task<PagedResultDto<{entity}Dto>> GetListAsync(Get{plural}Input input)
    {{
        var queryable = await _repository.GetQueryableAsync();
{filter_block}

        var totalCount = await AsyncExecuter.CountAsync(queryable);

        var query = queryable
            .OrderBy(input.Sorting.IsNullOrWhiteSpace() ? nameof({entity}.{default_sort_field}) : input.Sorting)
            .Skip(input.SkipCount)
            .Take(input.MaxResultCount);

        var items = await AsyncExecuter.ToListAsync(query);
        return new PagedResultDto<{entity}Dto>(
            totalCount,
            ObjectMapper.Map<List<{entity}>, List<{entity}Dto>>(items));
    }}

    [Authorize({root_ns}Permissions.{plural}.Create)]
    public async Task<{entity}Dto> CreateAsync(CreateUpdate{entity}Dto input)
    {{
        var entity = new {entity}(GuidGenerator.Create(), {ctor_args});
        await _repository.InsertAsync(entity);
        return ObjectMapper.Map<{entity}, {entity}Dto>(entity);
    }}

    [Authorize({root_ns}Permissions.{plural}.Edit)]
    public async Task<{entity}Dto> UpdateAsync(Guid id, CreateUpdate{entity}Dto input)
    {{
        var entity = await _repository.GetAsync(id);
        entity.Update({update_args});
        await _repository.UpdateAsync(entity);
        return ObjectMapper.Map<{entity}, {entity}Dto>(entity);
    }}

    [Authorize({root_ns}Permissions.{plural}.Delete)]
    public async Task DeleteAsync(Guid id)
    {{
        await _repository.DeleteAsync(id);
    }}
{optional_methods}{excel_block}{apply_filter_method}}}
"""


def _detect_mongo_context_class(ctx: AbpContext) -> str:
    """Return the real MongoDbContext class name (e.g. FooMongoDbContext).

    Prefer what's actually in the solution; fall back to the ABP convention
    ({Root}MongoDbContext for layered, {Root}DbContext for the historical
    single-project layout)."""
    sln = Path(ctx.solution_root) if ctx.solution_root else None
    if sln and sln.is_dir():
        for cs in sln.rglob("*MongoDbContext.cs"):
            return cs.stem
    if (ctx.template_type or "nolayers") in ("layered", "microservice"):
        return f"{ctx.root_namespace}MongoDbContext"
    return f"{ctx.root_namespace}DbContext"


def cs_custom_repo_interface(entity: str, plural: str, ns: str,
                             entities_ns: str, dtos_ns: str,
                             props: Optional[list[Prop]] = None,
                             layered: bool = False) -> str:
    if layered:
        # Domain-safe signature: the Domain layer must not reference
        # Application.Contracts, so we expose a primitive `filterText` + paging
        # contract instead of taking Get{Plural}Input. Structured per-field
        # filtering stays in the AppService — the ABP-idiomatic site for
        # application-level filtering in a layered solution.
        return f"""using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using {entities_ns};
using Volo.Abp.Domain.Repositories;

namespace {ns};

public interface I{entity}Repository : IRepository<{entity}, Guid>
{{
    Task<List<{entity}>> GetListAsync(
        string? filterText = null,
        string? sorting = null,
        int maxResultCount = int.MaxValue,
        int skipCount = 0,
        CancellationToken cancellationToken = default);

    Task<long> GetCountAsync(
        string? filterText = null,
        CancellationToken cancellationToken = default);
}}
"""
    return f"""using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using {entities_ns};
using {dtos_ns};
using Volo.Abp.Domain.Repositories;

namespace {ns};

public interface I{entity}Repository : IRepository<{entity}, Guid>
{{
    Task<List<{entity}>> GetListAsync(
        Get{plural}Input input,
        CancellationToken cancellationToken = default);

    Task<long> GetCountAsync(
        Get{plural}Input input,
        CancellationToken cancellationToken = default);

    Task DeleteAllAsync(
        Get{plural}Input input,
        CancellationToken cancellationToken = default);
}}
"""


def cs_mongo_repo(entity: str, plural: str, ns: str, entities_ns: str,
                  dtos_ns: str, project_ns: str, props: list[Prop],
                  filters: list[FilterSpec], layered: bool = False,
                  context_class: Optional[str] = None,
                  data_ns: Optional[str] = None) -> str:
    context_class = context_class or f"{project_ns}DbContext"

    if layered:
        # Layered impl: matches the Domain-safe interface (filterText + paging).
        # The MongoDB project references Domain (entity + I{Entity}Repository live
        # there) but NOT Application.Contracts, so no Get{Plural}Input here.
        text_fields = [p.name for p in props if p.type == "string"][:3]
        if text_fields:
            chain = " ||\n                ".join(
                f"(c.{fld} != null && c.{fld}.ToLower().Contains(__t))" if any(
                    p.name == fld and p.nullable for p in props
                ) else f"c.{fld}.ToLower().Contains(__t)"
                for fld in text_fields
            )
            text_filter = f"""        if (!string.IsNullOrWhiteSpace(filterText))
        {{
            var __t = filterText.Trim().ToLowerInvariant();
            queryable = queryable.Where(c =>
                {chain});
        }}"""
        else:
            text_filter = "        // No string properties available for text search."
        default_sort = props[0].name if props else "Id"
        return f"""using System;
using System.Collections.Generic;
using System.Linq;
using System.Linq.Dynamic.Core;
using System.Threading;
using System.Threading.Tasks;
using {entities_ns};
using MongoDB.Driver.Linq;
using Volo.Abp.Domain.Repositories.MongoDB;
using Volo.Abp.MongoDB;

namespace {ns};

public class Mongo{entity}Repository :
    MongoDbRepository<{context_class}, {entity}, Guid>,
    I{entity}Repository
{{
    public Mongo{entity}Repository(IMongoDbContextProvider<{context_class}> provider)
        : base(provider) {{ }}

    public async Task<List<{entity}>> GetListAsync(
        string? filterText = null,
        string? sorting = null,
        int maxResultCount = int.MaxValue,
        int skipCount = 0,
        CancellationToken cancellationToken = default)
    {{
        var queryable = await GetQueryableAsync(cancellationToken);
        queryable = (IMongoQueryable<{entity}>)ApplyFilter(queryable, filterText);
        queryable = (IMongoQueryable<{entity}>)queryable
            .OrderBy(sorting.IsNullOrWhiteSpace() ? nameof({entity}.{default_sort}) : sorting!)
            .Skip(skipCount)
            .Take(maxResultCount);
        return await queryable.ToListAsync(GetCancellationToken(cancellationToken));
    }}

    public async Task<long> GetCountAsync(
        string? filterText = null,
        CancellationToken cancellationToken = default)
    {{
        var queryable = await GetQueryableAsync(cancellationToken);
        queryable = (IMongoQueryable<{entity}>)ApplyFilter(queryable, filterText);
        return await queryable.LongCountAsync(GetCancellationToken(cancellationToken));
    }}

    protected virtual IQueryable<{entity}> ApplyFilter(IQueryable<{entity}> queryable, string? filterText)
    {{
{text_filter}
        return queryable;
    }}
}}
"""

    where_lines: list[str] = []
    for f in filters:
        if f.kind == "text":
            # Case-insensitive substring search: ToLower() on both sides.
            # MongoDB LINQ translates to $toLower → $regexMatch (single
            # round-trip); EF Core to LOWER(field) (single SQL statement).
            # See abp-feature-dev/references/filter-design.md.
            fields = f.args or [p.name for p in props if p.type == "string"][:3]
            chain = " ||\n                ".join(
                f"(c.{fld} != null && c.{fld}.ToLower().Contains(__t))" if any(
                    p.name == fld and p.nullable for p in props
                ) else f"c.{fld}.ToLower().Contains(__t)"
                for fld in fields
            )
            where_lines.append(f"""        if (!string.IsNullOrWhiteSpace(input.{f.name}))
        {{
            var __t = input.{f.name}.Trim().ToLowerInvariant();
            queryable = queryable.Where(c => {chain});
        }}""")
        elif f.kind == "string":
            # Case-insensitive exact match.
            where_lines.append(f"""        queryable = queryable.WhereIf(
            !string.IsNullOrWhiteSpace(input.{f.name}),
            c => c.{f.name}.ToLower() == input.{f.name}!.Trim().ToLowerInvariant());""")
        elif f.kind == "enum":
            where_lines.append(f"""        queryable = queryable.WhereIf(
            input.{f.name}.HasValue,
            c => c.{f.name} == input.{f.name}!.Value);""")
        elif f.kind == "bool":
            where_lines.append(f"""        queryable = queryable.WhereIf(
            input.{f.name}.HasValue,
            c => c.{f.name} == input.{f.name}!.Value);""")
        elif f.kind == "dateRange":
            where_lines.append(f"""        queryable = queryable.WhereIf(
            input.{f.name}From.HasValue,
            c => c.{f.name} >= input.{f.name}From!.Value);
        queryable = queryable.WhereIf(
            input.{f.name}To.HasValue,
            c => c.{f.name} <= input.{f.name}To!.Value);""")
        elif f.kind == "numRange":
            where_lines.append(f"""        queryable = queryable.WhereIf(
            input.{f.name}Min.HasValue,
            c => c.{f.name} >= input.{f.name}Min!.Value);
        queryable = queryable.WhereIf(
            input.{f.name}Max.HasValue,
            c => c.{f.name} <= input.{f.name}Max!.Value);""")
        elif f.kind == "guid":
            where_lines.append(f"""        queryable = queryable.WhereIf(
            input.{f.name}.HasValue,
            c => c.{f.name} == input.{f.name}!.Value);""")

    apply_filter = "\n\n".join(where_lines) if where_lines else "        return queryable;"
    default_sort = props[0].name if props else "Id"

    return f"""using System;
using System.Collections.Generic;
using System.Linq;
using System.Linq.Dynamic.Core;
using System.Threading;
using System.Threading.Tasks;
using {entities_ns};
using {dtos_ns};
using {project_ns}.Data;
using MongoDB.Driver.Linq;
using Volo.Abp.Domain.Repositories.MongoDB;
using Volo.Abp.MongoDB;

namespace {ns};

public class Mongo{entity}Repository :
    MongoDbRepository<{context_class}, {entity}, Guid>,
    I{entity}Repository
{{
    public Mongo{entity}Repository(IMongoDbContextProvider<{context_class}> provider)
        : base(provider) {{ }}

    public async Task<List<{entity}>> GetListAsync(
        Get{plural}Input input,
        CancellationToken cancellationToken = default)
    {{
        var queryable = await GetQueryableAsync(cancellationToken);
        queryable = (IMongoQueryable<{entity}>)ApplyFilter(queryable, input);
        queryable = (IMongoQueryable<{entity}>)queryable
            .OrderBy(input.Sorting.IsNullOrWhiteSpace() ? nameof({entity}.{default_sort}) : input.Sorting)
            .Skip(input.SkipCount)
            .Take(input.MaxResultCount);
        return await queryable.ToListAsync(GetCancellationToken(cancellationToken));
    }}

    public async Task<long> GetCountAsync(
        Get{plural}Input input,
        CancellationToken cancellationToken = default)
    {{
        var queryable = await GetQueryableAsync(cancellationToken);
        queryable = (IMongoQueryable<{entity}>)ApplyFilter(queryable, input);
        return await queryable.LongCountAsync(GetCancellationToken(cancellationToken));
    }}

    public async Task DeleteAllAsync(
        Get{plural}Input input,
        CancellationToken cancellationToken = default)
    {{
        var queryable = await GetQueryableAsync(cancellationToken);
        queryable = (IMongoQueryable<{entity}>)ApplyFilter(queryable, input);
        var ids = await queryable.Select(c => c.Id).ToListAsync(GetCancellationToken(cancellationToken));
        await DeleteManyAsync(ids, cancellationToken: GetCancellationToken(cancellationToken));
    }}

    protected virtual IQueryable<{entity}> ApplyFilter(IQueryable<{entity}> queryable, Get{plural}Input input)
    {{
{apply_filter}
        return queryable;
    }}
}}
"""


# --- Snippet generators (for manual merging) -------------------------------
def snippet_permissions(root_ns: str, plural: str, multi_tenant: bool) -> str:
    side = ", MultiTenancySides.Tenant" if multi_tenant else ""
    return f"""// =============================================================================
//  Permissions snippet — merge into your project's Permissions files manually.
// =============================================================================

// ---- 1) {root_ns}Permissions.cs ---------------------------------------------
//      Add this static class inside the {root_ns}Permissions class:

    public static class {plural}
    {{
        public const string Default = GroupName + ".{plural}";
        public const string Create  = Default + ".Create";
        public const string Edit    = Default + ".Edit";
        public const string Delete  = Default + ".Delete";
    }}

// ---- 2) {root_ns}PermissionDefinitionProvider.cs ----------------------------
//      Add this block inside the Define method:

    var {plural[0].lower() + plural[1:]}Permission = myGroup.AddPermission(
        {root_ns}Permissions.{plural}.Default,
        L("Permission:{plural}"){side});
    {plural[0].lower() + plural[1:]}Permission.AddChild(
        {root_ns}Permissions.{plural}.Create,
        L("Permission:{plural}.Create"){side});
    {plural[0].lower() + plural[1:]}Permission.AddChild(
        {root_ns}Permissions.{plural}.Edit,
        L("Permission:{plural}.Edit"){side});
    {plural[0].lower() + plural[1:]}Permission.AddChild(
        {root_ns}Permissions.{plural}.Delete,
        L("Permission:{plural}.Delete"){side});
"""


def snippet_mapper(entity: str, entities_ns: str, dtos_ns: str) -> str:
    return f"""// =============================================================================
//  Mapper snippet — append into your solution's central Mapperly mapper file:
//  the `*Mappers.cs` partial in the Application layer (layered: e.g.
//  {{Project}}ApplicationMappers.cs; single-project: e.g. {{Project}}Mappers.cs).
// =============================================================================

// 1) Add these usings to the top of the mapper file (if not already there):
using {entities_ns};
using {dtos_ns};

// 2) Append this class at the bottom of the file (next to other mappers):

[Mapper(RequiredMappingStrategy = RequiredMappingStrategy.Target)]
public partial class {entity}To{entity}DtoMapper : MapperBase<{entity}, {entity}Dto>
{{
    public override partial {entity}Dto Map({entity} source);
    public override partial void Map({entity} source, {entity}Dto destination);

    public List<{entity}Dto> MapToDtoList(List<{entity}> source)
        => source.Select(Map).ToList();
}}
"""


def snippet_localization(entity: str, plural: str, root_ns: str,
                         enums: list[EnumDecl],
                         lifecycle: Optional[LifecycleSpec]) -> str:
    """Generate a JSON snippet that should be merged into each language file."""
    keys: dict[str, str] = {
        f"Menu:{plural}": plural,
        plural: plural,
        entity: entity,
        f"New{entity}": f"New {entity.lower()}",
        f"{entity}DeletionConfirmationMessage": f"Are you sure to delete '{{0}}'?",
        f"Permission:{plural}": f"{entity} Management",
        f"Permission:{plural}.Create": f"Creating new {plural.lower()}",
        f"Permission:{plural}.Edit": f"Editing {plural.lower()}",
        f"Permission:{plural}.Delete": f"Deleting {plural.lower()}",
    }
    for e in enums:
        for i, v in enumerate(e.values):
            keys[f"Enum:{e.name}.{i}"] = v
    if lifecycle:
        keys[f"{root_ns}:{plural}:InvalidStatusTransition"] = (
            "Invalid status transition from {From} to {To}."
        )

    return json.dumps(keys, indent=2, ensure_ascii=False)


def snippet_next_steps(entity: str, plural: str, opts: Options,
                       lifecycle: Optional[LifecycleSpec],
                       multi_tenant: bool,
                       custom_repo: bool) -> str:
    blocks: list[list[str]] = []

    blocks.append([
        "**Register in DbContext** — delegate to `abp-mongodb`:",
        "   ```",
        f"   python <skills-root>/abp-mongodb/scripts/register_entity_in_context.py \\",
        f"       --entity {entity} --plural {plural}" + (
            " \\\n       --register-repository" if custom_repo else ""),
        "   ```",
    ])

    if multi_tenant:
        blocks.append([
            "**(Already done)** IMultiTenant added during scaffold. If the entity was",
            "   pre-existing and you wanted to make it tenant-aware retroactively:",
            "   `python <skills-root>/abp-multitenancy/scripts/add_multitenant_to_entity.py`",
        ])

    blocks.append([
        "**Merge permission snippet** — open `_permissions_snippet.txt` and integrate",
        "   the two blocks into your `Permissions` class and `PermissionDefinitionProvider`.",
    ])
    blocks.append([
        "**Grant new permissions in the tenant data seed contributor** — find a",
        f"   `*TenantDataSeedContributor.cs` (or any `IDataSeedContributor` that calls",
        f"   `IPermissionManager.SetForRoleAsync`) and add the 4 `{entity}.*` grants.",
        f"   Without this, the React permission guard hides the sidebar entry and the",
        f"   user has to grant manually via Admin Console. See `references/data-seeding.md`.",
        f"   Then run: `dotnet run --project <Host> -- --migrate-database` (or",
        f"   `./migrate-database.ps1`).",
    ])
    blocks.append([
        "**Merge mapper snippet** — open `_mapper_snippet.txt` and append into your",
        "   solution's central `*Mappers.cs` partial in the Application layer",
        "   (layered: `{Project}.Application/{Project}ApplicationMappers.cs`;",
        "   single-project: `ObjectMapping/{Project}Mappers.cs`).",
    ])
    blocks.append([
        "**Merge localization keys** — open `_localization_snippet.json` and integrate",
        "   the keys into each language file (`Localization/.../it.json`, `en.json`, ...).",
        "   After backend restart, **tell the user to hard-refresh** (Ctrl+F5): the React",
        "   i18n bundle is cached client-side, raw keys (`Enum:...`, `Menu:...`) will",
        "   appear until the next fetch of `/api/abp/application-localization`.",
    ])

    if lifecycle:
        blocks.append([
            f"**Lifecycle exposed** at `POST /api/app/{entity.lower()}/{{id}}/change-status`",
            f"   Allowed transitions: " + ", ".join(
                f"{a} → {b}" for a, b in lifecycle.transitions),
        ])

    if opts.excel_export:
        blocks.append([
            "**Add MiniExcel** to the project's csproj if missing:",
            "   ```xml",
            "   <PackageReference Include=\"MiniExcel\" Version=\"1.34.2\" />",
            "   ```",
        ])

    blocks.append([
        "**Run final validation:**",
        "   ```",
        f"   python <skills-root>/abp-feature-dev/scripts/verify_feature.py --entity {entity}",
        "   ```",
    ])

    blocks.append([
        "**Write tests:** delegate to `abp-testing`:",
        "   ```",
        f"   python <skills-root>/abp-testing/scripts/scaffold_test.py \\",
        f"       --entity {entity} --plural {plural}",
        "   ```",
    ])

    lines = [f"# Next steps for the {entity} feature", ""]
    for i, block in enumerate(blocks, start=1):
        lines.append(f"{i}. {block[0]}")
        lines.extend(block[1:])
        lines.append("")
    return "\n".join(lines)


# --- File writing helpers --------------------------------------------------
_NAMESPACE_RE = re.compile(r"^namespace\s+([\w.]+)\s*;", re.MULTILINE)


def _strip_self_using(content: str) -> str:
    """Drop `using N;` lines when the file itself declares `namespace N;`.

    In the layered template entity, DTO, AppService interface and implementation
    for one aggregate all share the namespace `Root.Plural` (they only differ by
    physical project). The builders below emit cross-references like
    `using {entities_ns};` that are correct for nolayers but become a redundant
    self-import in layered. Rather than special-case every builder, we remove the
    self-import here. Project references (which actually make the types visible)
    are already wired by the ABP layered template, so nothing else is needed."""
    m = _NAMESPACE_RE.search(content)
    if not m:
        return content
    own = m.group(1)
    lines = [ln for ln in content.splitlines() if ln.strip() != f"using {own};"]
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


def _write(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        print(f"[skip] {path} (use --force to overwrite)")
        return False
    if path.suffix == ".cs":
        content = _strip_self_using(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[write] {path}")
    return True


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        ans = input(f"{label}{suffix}: ").strip()
    except EOFError:
        ans = ""
    return ans or default


def _yes_no(s: str) -> bool:
    return s.strip().lower() in {"yes", "y", "true", "1", "si", "sì"}


# --- Main orchestration ----------------------------------------------------
def scaffold(ctx: AbpContext, entity: str, plural: str,
             props: list[Prop], enums: list[EnumDecl],
             filters: list[FilterSpec], lifecycle: Optional[LifecycleSpec],
             opts: Options, output_root: Optional[Path], force: bool) -> int:
    root_ns = ctx.root_namespace
    project_ns = root_ns
    sln_root = Path(ctx.solution_root or os.getcwd())
    # `base` is the root onto which each artifact's solution-relative directory
    # is appended. Normally the solution root; --output redirects the whole tree
    # elsewhere (tests / dry-runs) while preserving the per-layer layout.
    base = Path(output_root) if output_root else sln_root

    def _loc(kind: str):
        return resolve_artifact(ctx, kind, plural)

    # Namespaces. In layered, entity/enum/dto/interface/impl all collapse onto
    # `Root.Plural`; in nolayers each carries its layer segment. The resolver
    # encodes both, so the builders just receive the right strings.
    entities_ns = _loc("entity").namespace
    enums_ns = _loc("enum").namespace
    dtos_ns = _loc("dto").namespace
    iface_ns = _loc("appservice_interface").namespace
    services_ns = _loc("appservice_impl").namespace
    data_ns = _loc("repo_interface").namespace      # custom repo interface (Domain)
    repo_impl_ns = _loc("repo_impl").namespace      # custom repo impl (data layer)

    # Directories — one per artifact, each rooted under `base`. In nolayers they
    # all sit inside the single project; in layered they fan out across projects.
    entities_dir = base / _loc("entity").dir
    enums_dir = base / _loc("enum").dir
    dtos_dir = base / _loc("dto").dir
    iface_dir = base / _loc("appservice_interface").dir
    services_dir = base / _loc("appservice_impl").dir
    data_dir = base / _loc("repo_interface").dir
    repo_impl_dir = base / _loc("repo_impl").dir
    error_codes_dir = base / _loc("error_codes").dir
    review_dir = entities_dir / "_review_artifacts"

    # 1) Entity
    _write(entities_dir / f"{entity}.cs",
           cs_entity(entity, plural, entities_ns, root_ns, props, enums, opts, lifecycle),
           force)

    # 2) Enums (one file per enum). In layered these land in Domain.Shared so the
    #    Application.Contracts DTOs can reference them without pulling in Domain.
    for e in enums:
        _write(enums_dir / f"{e.name}.cs", cs_enum(e, enums_ns), force)

    # 3) Domain error codes (only if lifecycle, only if file doesn't already
    # have the namespace block — caller can merge manually)
    if lifecycle:
        code_file = error_codes_dir / f"{root_ns}DomainErrorCodes.cs"
        if not code_file.exists():
            _write(code_file,
                   cs_domain_error_codes(root_ns, plural, ["InvalidStatusTransition"]),
                   force)
        else:
            # Add a merge snippet — don't try to rewrite existing file
            snippet = (
                f"// Merge into {root_ns}DomainErrorCodes.cs — add this nested class:\n\n"
                f"public static class {plural}\n{{\n"
                f"    public const string InvalidStatusTransition = "
                f"\"{root_ns}:{plural}:InvalidStatusTransition\";\n}}\n"
            )
            _write(review_dir / "_domain_error_codes_snippet.txt", snippet, True)

    # 4) DTOs
    _write(dtos_dir / f"{entity}Dto.cs",
           cs_dto(entity, dtos_ns, props, opts, lifecycle, dtos_ns, entities_ns),
           force)
    _write(dtos_dir / f"CreateUpdate{entity}Dto.cs",
           cs_create_update_dto(entity, dtos_ns, entities_ns, props, opts), force)
    if filters or True:  # always emit the typed input even if empty
        _write(dtos_dir / f"Get{plural}Input.cs",
               cs_get_input(plural, dtos_ns, entities_ns, filters), force)
    if lifecycle:
        _write(dtos_dir / f"Change{entity}StatusDto.cs",
               cs_change_status_dto(entity, dtos_ns, entities_ns, lifecycle), force)
    if opts.lookup:
        _write(dtos_dir / f"{entity}LookupDto.cs",
               cs_lookup_dto(entity, dtos_ns), force)
    if opts.excel_export:
        _write(dtos_dir / f"{entity}ExcelDto.cs",
               cs_excel_dto(entity, dtos_ns, props), force)
        # The shared DownloadTokenResultDto — only write if not present. Lives in
        # the same contracts layer as the other DTOs (resolved with a "Shared"
        # aggregate name).
        shared_loc = resolve_artifact(ctx, "dto", "Shared")
        shared = base / shared_loc.dir / "DownloadTokenResultDto.cs"
        if not shared.exists():
            _write(shared,
                   f"""namespace {shared_loc.namespace};

public class DownloadTokenResultDto
{{
    public string Token {{ get; set; }} = default!;
}}
""", True)

    # 5) AppService interface (Application.Contracts in layered) + implementation
    #    (Application in layered). In nolayers both land in Services/{Plural}.
    if not opts.no_app_service:
        _write(iface_dir / f"I{entity}AppService.cs",
               cs_app_service_interface(entity, plural, iface_ns, dtos_ns, opts, lifecycle),
               force)
        _write(services_dir / f"{entity}AppService.cs",
               cs_app_service(entity, plural, root_ns, project_ns, services_ns,
                              dtos_ns, entities_ns, props, filters, opts, lifecycle),
               force)

    # 6) Custom repository — interface in Domain, implementation in the data
    #    layer. In layered the Domain interface must not depend on
    #    Application.Contracts, so its layered variant takes primitive filter
    #    parameters instead of the Get{Plural}Input DTO.
    if opts.custom_repository:
        layered = (ctx.template_type or "nolayers") in ("layered", "microservice")
        context_class = _detect_mongo_context_class(ctx)
        _write(data_dir / f"I{entity}Repository.cs",
               cs_custom_repo_interface(entity, plural, data_ns, entities_ns,
                                        dtos_ns, props, layered),
               force)
        _write(repo_impl_dir / f"Mongo{entity}Repository.cs",
               cs_mongo_repo(entity, plural, repo_impl_ns, entities_ns, dtos_ns,
                             project_ns, props, filters, layered,
                             context_class, data_ns),
               force)

    # 7) Review artifacts (snippets)
    _write(review_dir / "_permissions_snippet.txt",
           snippet_permissions(root_ns, plural, opts.multi_tenant), True)
    _write(review_dir / "_mapper_snippet.txt",
           snippet_mapper(entity, entities_ns, dtos_ns), True)
    _write(review_dir / "_localization_snippet.json",
           snippet_localization(entity, plural, root_ns, enums, lifecycle), True)
    _write(review_dir / "_next_steps.md",
           snippet_next_steps(entity, plural, opts, lifecycle,
                              opts.multi_tenant, opts.custom_repository),
           True)

    print()
    print(f"[OK] Scaffolded {entity} feature ({ctx.template_type}) under {base}")
    print(f"     See {review_dir / '_next_steps.md'} for the finalization checklist.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold an ABP feature folder")
    parser.add_argument("--name", help="Entity name (PascalCase singular)")
    parser.add_argument("--plural", help="Plural / folder name")
    parser.add_argument("--properties", help='Property spec — see SKILL.md')
    parser.add_argument("--enums", help='Enum spec: "Name:V1,V2;Name2:..."')
    parser.add_argument("--audit", choices=["Entity", "Audited", "FullAudited"],
                        default="Audited")
    parser.add_argument("--multi-tenant", default="auto",
                        help="yes|no|auto (default: auto-detect from project)")
    parser.add_argument("--concurrency", default="no")
    parser.add_argument("--filters", help="Filter spec — see SKILL.md")
    parser.add_argument("--lifecycle", help="Lifecycle spec — see SKILL.md")
    parser.add_argument("--bulk-delete", default="no")
    parser.add_argument("--excel-export", default="no")
    parser.add_argument("--lookup", default="no")
    parser.add_argument("--lookup-display", default="DisplayName")
    parser.add_argument("--custom-repository", default="auto",
                        help="yes|no|auto (default: yes if >3 filters)")
    parser.add_argument("--split-create-update", default="no")
    parser.add_argument("--public-setters", action="store_true",
                        help="Generate entity with public setters (trivial CRUD only)")
    parser.add_argument("--no-app-service", action="store_true",
                        help="Skip AppService + interface (entity-only port)")
    parser.add_argument("--output", help="Output root (defaults to project_root)")
    parser.add_argument("--cwd", help="Override working directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    ctx = load_or_prompt_config(args.cwd)

    name = args.name or _prompt("Entity name (PascalCase)")
    if not name:
        print("Entity name is required.", file=sys.stderr)
        return 2
    plural = args.plural or _prompt("Plural / folder name", name + "s")

    props_spec = args.properties
    if props_spec is None:
        props_spec = _prompt(
            "Properties (Name:Type[?][@len][=default], comma-separated)",
            "Name:string",
        )
    props = parse_properties(props_spec)
    enums = parse_enums(args.enums)
    filters = parse_filters(args.filters, props, enums)
    lifecycle = parse_lifecycle(args.lifecycle, enums)

    # Auto-multi-tenant: peek at the project's main module for IsMultiTenant=true
    multi_tenant = False
    if args.multi_tenant == "yes":
        multi_tenant = True
    elif args.multi_tenant == "no":
        multi_tenant = False
    else:  # auto
        sln = Path(ctx.solution_root) if ctx.solution_root else Path.cwd()
        for module in sln.rglob("*Module.cs"):
            try:
                t = module.read_text(encoding="utf-8", errors="ignore")
                if re.search(r"IsMultiTenant\s*=\s*true", t):
                    multi_tenant = True
                    break
            except OSError:
                continue

    # Auto-custom-repo: in nolayers, default to yes when there are many filters
    # (>3) — the single project can host the filter chain freely. In layered,
    # default to NO: the ABP-idiomatic approach keeps application-level filtering
    # in the AppService, and a Domain repository must stay free of
    # Application.Contracts types. Pass --custom-repository yes to force it.
    layered_tt = (ctx.template_type or "nolayers") in ("layered", "microservice")
    if args.custom_repository == "yes":
        custom_repo = True
    elif args.custom_repository == "no":
        custom_repo = False
    else:
        custom_repo = (not layered_tt) and len(filters) > 3

    opts = Options(
        audit=args.audit,
        multi_tenant=multi_tenant,
        concurrency=_yes_no(args.concurrency),
        bulk_delete=_yes_no(args.bulk_delete),
        excel_export=_yes_no(args.excel_export),
        lookup=_yes_no(args.lookup),
        lookup_display=args.lookup_display,
        custom_repository=custom_repo,
        split_create_update=_yes_no(args.split_create_update),
        public_setters=args.public_setters,
        no_app_service=args.no_app_service,
    )

    output_root = Path(args.output) if args.output else None
    return scaffold(ctx, name, plural, props, enums, filters, lifecycle,
                    opts, output_root, args.force)


if __name__ == "__main__":
    sys.exit(main())
