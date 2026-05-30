"""Helpers for the session-handoff skill.

Three subcommands:

    path    Print the canonical handoff file path inside the OS temp directory
            (never the workspace). Creates the parent folder.

    digest  Turn a raw session transcript (a large, noisy Claude Code / agent
            `.jsonl`, or a plain-text log) into a compact, readable markdown
            transcript: user/assistant text plus summarized tool calls, with big
            tool outputs truncated and the middle elided to fit a budget while
            keeping the goal-bearing start and the state-bearing end. Use this
            when you are asked to hand off a session that lives in a FILE rather
            than in your own live context.

    redact  Sweep a finished handoff document for credentials and high-confidence
            sensitive data, replacing each hit with a TYPED placeholder such as
            [REDACTED:github-token]. This is a safety net that runs AFTER the
            agent has written the doc -- it does not replace the agent's own
            judgement about contextual PII (see references/redaction.md).

Design notes:
- Credentials are redacted by default: a leaked live key costs everything, a
  false redaction costs nothing.
- Env var NAMES are preserved, only their VALUES are redacted.
- Connection strings / URLs keep their skeleton; only the password is dropped.
- Ordinary identifiers (paths, hostnames, env var names, commit SHAs, the
  author's own attribution) are intentionally left alone to keep the doc useful.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# --- path -------------------------------------------------------------------

def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:50] or "session"


def cmd_path(args: argparse.Namespace) -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"handoff-{stamp}"
    if args.slug:
        name += f"-{_slugify(args.slug)}"
    target = Path(tempfile.gettempdir()) / "handoffs" / f"{name}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    print(target)
    return 0


# --- digest -----------------------------------------------------------------

def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f" …[+{len(text) - limit} chars]"


def _flatten_result(content: object) -> str:
    """A tool_result's content may be a string or a list of text blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "image":
                    parts.append("[image]")
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(p for p in parts if p)
    return ""


def _render_blocks(content: object, max_block: int, max_result: int) -> list[str]:
    if isinstance(content, str):
        t = _truncate(content, max_block)
        return [t] if t else []
    if not isinstance(content, list):
        return []
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            t = _truncate(block.get("text", ""), max_block)
            if t:
                parts.append(t)
        elif btype == "thinking":
            continue  # internal reasoning is not part of the handed-off record
        elif btype == "tool_use":
            name = block.get("name", "?")
            try:
                inp = json.dumps(block.get("input", {}), ensure_ascii=False)
            except Exception:
                inp = str(block.get("input", {}))
            parts.append(f"→ tool: {name}({_truncate(inp, 200)})")
        elif btype == "tool_result":
            tag = "result(error)" if block.get("is_error") else "result"
            parts.append(f"← {tag}: {_truncate(_flatten_result(block.get('content')), max_result)}")
        elif btype == "image":
            parts.append("[image]")
    return parts


def _digest_jsonl(lines: list[str], max_block: int, max_result: int) -> list[tuple[str, str]]:
    rendered: list[tuple[str, str]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("type") == "summary" and obj.get("summary"):
            rendered.append(("SUMMARY", _truncate(str(obj["summary"]), max_block)))
            continue
        if obj.get("isMeta") or obj.get("type") == "system":
            continue
        msg = obj.get("message")
        if not isinstance(msg, dict):
            continue
        role = (msg.get("role") or obj.get("type") or "?").upper()
        parts = _render_blocks(msg.get("content"), max_block, max_result)
        if parts:
            rendered.append((role, "\n".join(parts)))
    return rendered


def cmd_digest(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.is_file():
        print(f"[error] no such file: {path}", file=sys.stderr)
        return 2

    raw = path.read_text(encoding="utf-8", errors="replace")
    looks_jsonl = path.suffix.lower() == ".jsonl" or raw.lstrip().startswith("{")

    if looks_jsonl:
        rendered = _digest_jsonl(raw.splitlines(), args.max_block, args.max_result)
    else:
        # Plain-text log: keep as one block, still subject to the global budget.
        rendered = [("TRANSCRIPT", raw)]

    header = f"# Session transcript (digested from {path.name})\n\n"
    blocks = [f"## {role}\n{text}\n" for role, text in rendered]
    full = header + "\n".join(blocks)

    if len(full) <= args.max_chars:
        result = full
    else:
        head_budget = int(args.max_chars * 0.55)
        tail_budget = args.max_chars - head_budget
        head: list[str] = []
        used = 0
        for b in blocks:
            if used + len(b) > head_budget:
                break
            head.append(b)
            used += len(b)
        tail: list[str] = []
        used = 0
        for b in reversed(blocks):
            if used + len(b) > tail_budget:
                break
            tail.append(b)
            used += len(b)
        tail.reverse()
        elided = len(blocks) - len(head) - len(tail)
        result = (header + "\n".join(head)
                  + f"\n\n... [{elided} message(s) elided to fit the budget; "
                  + "goal-bearing start and state-bearing end kept] ...\n\n"
                  + "\n".join(tail))

    print(f"[digest] {len(blocks)} message(s) parsed; output {len(result)} chars",
          file=sys.stderr)
    if args.out:
        Path(args.out).write_text(result, encoding="utf-8")
        print(f"[digest] wrote -> {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(result)
    return 0


# --- redact -----------------------------------------------------------------

# (name, pattern, replacement). Patterns adapted from the gitleaks ruleset and
# detect-secrets. Keep the placeholder typed so the next agent knows what kind
# of credential lived there without leaking it.
SIMPLE_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("aws-access-key-id",
     re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z2-7]{16}\b"),
     "[REDACTED:aws-access-key-id]"),
    ("github-token",
     re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36}\b|\bgithub_pat_[0-9A-Za-z]{22}_[0-9A-Za-z]{59}\b"),
     "[REDACTED:github-token]"),
    ("gitlab-token",
     re.compile(r"\bglpat-[0-9A-Za-z_-]{20}\b"),
     "[REDACTED:gitlab-token]"),
    ("slack-token",
     re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
     "[REDACTED:slack-token]"),
    ("google-api-key",
     re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
     "[REDACTED:google-api-key]"),
    ("google-oauth-secret",
     re.compile(r"\bGOCSPX-[0-9A-Za-z_-]{28}\b"),
     "[REDACTED:google-oauth-secret]"),
    ("llm-api-key",
     re.compile(r"\bsk-ant-[0-9A-Za-z_-]{20,}\b|\bsk-(?:proj-)?[0-9A-Za-z_-]{20,}\b"),
     "[REDACTED:llm-api-key]"),
    ("stripe-key",
     re.compile(r"\b(?:sk|rk|pk)_(?:test|live|prod)_[0-9A-Za-z]{10,}\b"),
     "[REDACTED:stripe-key]"),
    ("sendgrid-key",
     re.compile(r"\bSG\.[0-9A-Za-z_-]{22}\.[0-9A-Za-z_-]{43}\b"),
     "[REDACTED:sendgrid-key]"),
    ("jwt",
     re.compile(r"\beyJ[0-9A-Za-z_-]{6,}\.eyJ[0-9A-Za-z_-]{6,}\.[0-9A-Za-z_-]{6,}\b"),
     "[REDACTED:jwt]"),
    # PII that is unambiguous enough to redact automatically.
    ("us-ssn",
     re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
     "[REDACTED:ssn]"),
]

# Multiline PEM / SSH private key block.
PEM_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)

# scheme://user:password@host  -> keep skeleton, drop the password segment.
URL_CRED_RE = re.compile(r"\b([a-z][a-z0-9+.\-]*://[^\s:/@]+):([^\s:/@]+)@")

# Authorization: Bearer <token>  /  Authorization: Basic <blob>
AUTH_HEADER_RE = re.compile(
    r"(?i)(authorization\s*[:=]\s*(?:bearer|basic|token)\s+)([^\s'\"]+)")

# key = value where the key looks credential-ish. Keep the key, drop the value.
KV_SECRET_RE = re.compile(
    r"(?i)\b([a-z0-9_.\-]*(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
    r"client[_-]?secret|private[_-]?key|auth)[a-z0-9_.\-]*)\s*([:=])\s*"
    r"(['\"]?)([^\s'\"]{6,})(['\"]?)")

# Luhn check keeps credit-card redaction from nuking ordinary digit runs.
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_ok(digits: str) -> bool:
    nums = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(nums) <= 19:
        return False
    total, parity = 0, len(nums) % 2
    for i, n in enumerate(nums):
        if i % 2 == parity:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}

    def bump(kind: str, n: int = 1) -> None:
        if n:
            counts[kind] = counts.get(kind, 0) + n

    # 1. Multiline private keys first (collapse the whole block).
    text, n = PEM_RE.subn("[REDACTED:private-key]", text)
    bump("private-key", n)

    # 2. URL embedded credentials -> keep user + host.
    text, n = URL_CRED_RE.subn(r"\1:[REDACTED:url-password]@", text)
    bump("url-password", n)

    # 3. Authorization headers.
    text, n = AUTH_HEADER_RE.subn(r"\1[REDACTED:auth-token]", text)
    bump("auth-token", n)

    # 4. High-precision prefixed credentials and unambiguous PII.
    for kind, pat, repl in SIMPLE_PATTERNS:
        text, n = pat.subn(repl, text)
        bump(kind, n)

    # 5. credential-ish key=value (keep the name, drop the value).
    _SKIP_VALUES = {"bearer", "basic", "token", "negotiate", "digest"}

    def _kv(m: re.Match[str]) -> str:
        value = m.group(4)
        # Don't re-redact a value an earlier pass already handled, and don't
        # mistake an auth scheme word ("Bearer ...") for the secret itself.
        if value.startswith("[REDACTED") or value.lower() in _SKIP_VALUES:
            return m.group(0)
        return f"{m.group(1)}{m.group(2)} [REDACTED:secret]"

    before = text.count("[REDACTED:secret]")
    text = KV_SECRET_RE.sub(_kv, text)
    bump("secret", text.count("[REDACTED:secret]") - before)

    # 6. Luhn-valid credit cards.
    def _card(m: re.Match[str]) -> str:
        s = m.group(0)
        return "[REDACTED:credit-card]" if _luhn_ok(s) else s
    new_text = CARD_RE.sub(_card, text)
    bump("credit-card", new_text.count("[REDACTED:credit-card]")
         - text.count("[REDACTED:credit-card]"))
    text = new_text

    return text, counts


def cmd_redact(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.is_file():
        print(f"[error] no such file: {path}", file=sys.stderr)
        return 2
    original = path.read_text(encoding="utf-8")
    redacted, counts = redact_text(original)

    total = sum(counts.values())
    if total:
        summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()) if v)
        print(f"[redact] {total} replacement(s): {summary}", file=sys.stderr)
    else:
        print("[redact] no high-confidence secrets found "
              "(still review contextual PII by hand)", file=sys.stderr)

    if args.report_only:
        return 0
    if args.stdout:
        sys.stdout.write(redacted)
    else:
        path.write_text(redacted, encoding="utf-8")
        print(f"[redact] wrote sanitized doc -> {path}", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="session-handoff helpers")
    sub = parser.add_subparsers(dest="command", required=True)

    p_path = sub.add_parser("path", help="print the handoff path in the OS temp dir")
    p_path.add_argument("--slug", help="short topic slug appended to the filename")
    p_path.set_defaults(func=cmd_path)

    p_dig = sub.add_parser("digest", help="condense a raw session transcript into readable markdown")
    p_dig.add_argument("file", help="path to the session transcript (.jsonl or text)")
    p_dig.add_argument("--out", help="write the digest here instead of stdout")
    p_dig.add_argument("--max-chars", type=int, default=120000,
                       help="total budget; middle is elided if exceeded (default 120000)")
    p_dig.add_argument("--max-block", type=int, default=2000,
                       help="max chars kept per text message (default 2000)")
    p_dig.add_argument("--max-result", type=int, default=400,
                       help="max chars kept per tool result (default 400)")
    p_dig.set_defaults(func=cmd_digest)

    p_red = sub.add_parser("redact", help="sanitize a finished handoff document")
    p_red.add_argument("file", help="path to the handoff .md to sanitize in place")
    p_red.add_argument("--stdout", action="store_true",
                       help="print the sanitized text instead of writing in place")
    p_red.add_argument("--report-only", action="store_true",
                       help="only report what would be redacted; do not modify")
    p_red.set_defaults(func=cmd_redact)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
