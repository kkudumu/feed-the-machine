# Secret Patterns — Extended Pattern Library

Full regex pattern library for Phase 1 scanning. Tier 1 patterns are high-confidence; Tier 2 require surrounding context validation.

---

## Tier 1: High-Confidence Patterns (almost certainly real secrets)

These patterns have distinctive prefixes or structures that make false positives rare. Run in parallel.

```
# AWS
AKIA[0-9A-Z]{16}                                          # AWS Access Key ID
amzn\.mws\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}  # AWS MWS

# GitHub
ghp_[A-Za-z0-9_]{36}                                      # GitHub PAT (classic)
gho_[A-Za-z0-9_]{36}                                      # GitHub OAuth
ghu_[A-Za-z0-9_]{36}                                      # GitHub user token
ghs_[A-Za-z0-9_]{36}                                      # GitHub server token
github_pat_[A-Za-z0-9_]{82}                                # GitHub fine-grained PAT

# Slack
xoxb-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}           # Slack bot token
xoxp-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,34}        # Slack user token
xoxa-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,34}        # Slack app token
xoxr-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,34}        # Slack refresh token

# Google
AIza[0-9A-Za-z\-_]{35}                                    # Google API key

# Stripe
sk_live_[0-9a-zA-Z]{24,}                                  # Stripe secret key (live)
sk_test_[0-9a-zA-Z]{24,}                                  # Stripe secret key (test)
rk_live_[0-9a-zA-Z]{24,}                                  # Stripe restricted key

# Other services
SG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}               # SendGrid
SK[0-9a-fA-F]{32}                                          # Twilio
npm_[A-Za-z0-9]{36}                                        # npm token
pypi-[A-Za-z0-9\-_]{100,}                                 # PyPI token
glpat-[A-Za-z0-9\-_]{20,}                                 # GitLab PAT
-----BEGIN (RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----      # Private keys
```

---

## Tier 2: Context-Dependent Patterns (need surrounding context to confirm)

These match common assignment patterns. Check that the value isn't a placeholder, empty string, or env var reference before flagging:

```
# Generic key/secret assignments — flag if value looks real (not placeholder)
(api_key|apikey|api-key)\s*[:=]\s*["']?[A-Za-z0-9\-_]{16,}["']?
(secret|secret_key|client_secret)\s*[:=]\s*["']?[A-Za-z0-9\-_]{16,}["']?
(password|passwd|pwd)\s*[:=]\s*["']?[^\s"']{8,}["']?
(token|access_token|auth_token)\s*[:=]\s*["']?[A-Za-z0-9\-_.]{16,}["']?
(database_url|db_url|connection_string)\s*[:=]\s*["']?[^\s"']{20,}["']?

# Bearer tokens in code
bearer\s+[A-Za-z0-9\-._~+/]{20,}

# Webhook URLs with tokens
https://hooks\.slack\.com/services/T[A-Z0-9]{8,}/B[A-Z0-9]{8,}/[a-zA-Z0-9]{24}
```

---

## What to Ignore (false positive suppression)

Skip matches that are clearly not real secrets:

- Values that are `""`, `''`, `None`, `null`, `undefined`, `TODO`, `CHANGEME`, `your-key-here`, `xxx`, `placeholder`, `example`, `test`, `dummy`, `fake`, `sample`
- References to environment variables: `os.environ[`, `process.env.`, `ENV[`, `${`, `os.getenv(`
- Lines that are comments (`#`, `//`, `/*`, `--`)
- Files in `node_modules/`, `.git/`, `vendor/`, `__pycache__/`, `dist/`, `build/`
- Files that are themselves `.env.example`, `.env.sample`, `.env.template`
- Lock files (`package-lock.json`, `yarn.lock`, `Gemfile.lock`, `poetry.lock`)
- Test fixtures where the "secret" is obviously fake (e.g., `test_api_key = "sk_test_abc123"` in a test file — but still flag `sk_live_*` in test files, those are real)

---

## Severity Classification

After validation, findings are sorted by severity:

| Severity | Meaning |
|---|---|
| **CRITICAL** | Tier 1 match (high-confidence secret) in a tracked or staged file |
| **HIGH** | Tier 2 confirmed match in a tracked or staged file |
| **MEDIUM** | `.env` file not in `.gitignore`, or secret in a fallback default |
| **LOW** | Secret in a gitignored file but the gitignore rule might be fragile |

---

## Per-Finding Record Format

For each finding, record:
- **file**: absolute path
- **line**: line number
- **pattern**: which pattern matched
- **tier**: 1 or 2
- **value_preview**: first 8 chars + `...` + last 4 chars (never log the full secret)
- **context**: the surrounding code (with the secret value masked)
