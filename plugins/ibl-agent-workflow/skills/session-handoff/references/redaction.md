# Redaction guide

The handoff is written to a shared OS temp directory and handed to another
agent or person. Strip secrets and high-risk PII **before** saving. The bundled
`scripts/handoff.py redact <file>` automates the high-confidence cases; this
file is the rationale and the contextual judgement the script can't make.

## How scanners find secrets (so you can mimic them)

Three signals, in precision order: **prefix/structure** (`AKIA`, `ghp_`, `sk-`,
`xoxb-`, `AIza`, `eyJ…`) — highest precision; **keyword proximity** (a key named
`password`/`secret`/`token`/`apikey` next to a value); **entropy** (long opaque
random strings near a credential-ish name). You can't verify a key is live, so
**default to redacting on a format match** — assume it's real.

## Pattern table

| Type | Recognition | Placeholder |
|---|---|---|
| AWS access key id | `(AKIA|ASIA|ABIA|ACCA|A3T[A-Z0-9])[A-Z2-7]{16}` | `[REDACTED:aws-access-key-id]` |
| AWS secret key | 40-char base64 near `aws`/`secret` | `[REDACTED:aws-secret-key]` |
| GitHub token | `gh[pousr]_[0-9A-Za-z]{36}`, `github_pat_…` | `[REDACTED:github-token]` |
| GitLab PAT | `glpat-[\w-]{20}` | `[REDACTED:gitlab-token]` |
| Slack token | `xox[baprs]-…` | `[REDACTED:slack-token]` |
| Google API key | `AIza[0-9A-Za-z_-]{35}` | `[REDACTED:google-api-key]` |
| Google OAuth | `ya29\.…`, client secret `GOCSPX-…` | `[REDACTED:google-oauth-token]` |
| OpenAI / Anthropic | `sk-…`, `sk-ant-…`, `sk-proj-…` | `[REDACTED:llm-api-key]` |
| Stripe | `(sk|rk|pk)_(test|live|prod)_…` | `[REDACTED:stripe-key]` |
| JWT | `eyJ…\.eyJ…\.…` (3 base64url parts) | `[REDACTED:jwt]` |
| Bearer / Authorization | redact the token value | `Authorization: Bearer [REDACTED:auth-token]` |
| Private key (PEM/SSH) | `-----BEGIN … PRIVATE KEY-----` … `END` | `[REDACTED:private-key]` |
| Connection string | `scheme://user:pass@host` → drop the password | `postgres://user:[REDACTED:db-password]@host/db` |
| Basic-auth URL | `https://user:pass@host` → drop the password | `https://user:[REDACTED:url-password]@host` |
| Generic secret assignment | key (`api_key`/`secret`/`token`/`password`) `=`/`:` value | `<KEY>=[REDACTED:secret]` |
| Credit card (Luhn-valid) | 13–19 digits, card prefixes | `[REDACTED:credit-card]` |
| Email / phone / SSN | standard formats | `[REDACTED:email]` etc. — **selective, see below** |

## Principles

1. **Typed placeholders, never partial masks.** `[REDACTED:aws-secret-key]`
   tells the next agent *what kind* of credential lived there without leaking
   it. "First-4/last-4" masking narrows brute-force space — don't.
2. **Reference, don't inline.** Never paste the *contents* of `.env`,
   `credentials`, `id_rsa`, `*.pem`, `kubeconfig`, `.npmrc`, service-account
   JSON. Write the path: `See ./.env (not inlined — contains secrets)`.
3. **Default to redact for credentials when unsure.** False redaction costs
   nothing; a leaked live key costs everything.
4. **Don't over-redact ordinary identifiers.** Keep code, file paths,
   function/variable names, hostnames, public URLs, ticket IDs, commit SHAs,
   branch names, session ids, `author_session` values, slug identifiers,
   table/column names, **env var NAMES**, and the author's own attribution
   email. The bar: *could this single doc, leaked, harm or identify a private
   third party?* — not "is this technically personal data?".
5. **Keep the surrounding structure.** `STRIPE_KEY=[REDACTED:stripe-key]` tells
   the reader exactly what to supply without revealing it.
6. **Redact consistently.** Same secret → same placeholder (number them if
   relationships matter: `[REDACTED:jwt-1]`).

## Pitfalls

- **Secrets in URLs** — query strings (`?token=`, `&sig=`, S3 `X-Amz-Signature=`)
  and userinfo (`user:pass@host`). Most-missed leak.
- **Multiline PEM/SSH keys** — collapse the whole `BEGIN…END` block to one
  placeholder; don't redact line-by-line.
- **Env NAME vs VALUE** — keep the name, drop the value. Never invert.
- **Base64 / JSON blobs** — service-account JSON, kubeconfig hide creds inside
  structure; if you can't cleanly redact the inner fields, redact the whole blob
  and reference its path.
- **Quoted logs / stack traces / shell history** — `curl -H "Authorization:
  Bearer …"`, `export AWS_SECRET_ACCESS_KEY=…`, DSNs echoed in errors. Scan
  fenced blocks with the same rules as prose.
- **JWT payloads aren't encrypted** — the middle segment decodes to email/roles;
  redact the whole token.
- **Over-redaction traps** — leave placeholders already in the source
  (`your-api-key-here`, `<token>`, `xxxx`), public keys (`ssh-rsa AAAA…`,
  `BEGIN PUBLIC KEY`), and UUIDs/SHAs that merely look random.

## Redaction pass checklist (run on the finished doc, before saving)

1. Run `scripts/handoff.py redact <file>` — it handles prefixed credentials,
   PEM blocks, connection strings, Authorization headers, credential `key=value`,
   credit cards, and SSNs.
2. **Contextual sweep the script can't do:** redact third-party PII (other
   people's emails, phones, home addresses, national IDs); keep the author's own
   attribution.
3. Re-check every URL for embedded userinfo and sensitive query params.
4. Confirm no `.env` / `*.pem` / `kubeconfig` / service-account contents were
   pasted — replace with path + "not inlined" note.
5. Confirm env var NAMES survived and only VALUES were dropped.
6. Confirm the doc still conveys the technical state — you protected privacy
   without nuking it into uselessness.
