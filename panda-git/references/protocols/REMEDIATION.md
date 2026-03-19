# Remediation Protocol — Auto-Fix Steps

Detailed remediation steps for secrets found during Phase 1–2 scanning. Apply in sequence for each finding.

---

## Phase 3: Auto-Remediate

For each finding, apply the appropriate fix automatically. The goal is to make the code safe without breaking functionality.

### Step 1: Ensure .env infrastructure exists

Check for a `.env` file in the project root. If it doesn't exist, create one with a header comment:

```
# Environment variables — DO NOT COMMIT THIS FILE
# Copy .env.example for the template, fill in real values locally
```

Check `.gitignore` for `.env` coverage. If missing, add:
```
# Environment files with secrets
.env
.env.local
.env.production
.env.staging
.env.*.local
```

### Step 2: Extract secrets to .env

For each finding:

1. **Choose an env var name** — derive it from the context. If the code says `STRIPE_API_KEY = "sk_live_..."`, the env var is `STRIPE_API_KEY`. If it says `api_key: "AIza..."`, infer from the file/service context (e.g., `GOOGLE_API_KEY`). Use SCREAMING_SNAKE_CASE.

2. **Add to .env** — append `VAR_NAME=<actual-secret-value>` to `.env`. If the var already exists, don't duplicate it.

3. **Add to .env.example** — create or update `.env.example` with `VAR_NAME=your-value-here` so other developers know the variable exists without seeing the real value.

### Step 3: Refactor source files

Replace the hardcoded secret with an env var reference. Match the language/framework:

| Language | Pattern |
|---|---|
| Python | `os.environ["VAR_NAME"]` or `os.getenv("VAR_NAME")` (match existing style in file) |
| JavaScript/TypeScript | `process.env.VAR_NAME` |
| Ruby | `ENV["VAR_NAME"]` or `ENV.fetch("VAR_NAME")` |
| Go | `os.Getenv("VAR_NAME")` |
| Java | `System.getenv("VAR_NAME")` |
| Shell/Bash | `$VAR_NAME` or `${VAR_NAME}` |
| YAML/JSON config | `${VAR_NAME}` (if the framework supports interpolation) or add a comment pointing to the env var |

If the file doesn't already import the env-reading module (e.g., `import os` in Python, `require('dotenv').config()` in Node), add the import. Check if the project uses `python-dotenv`, `dotenv` (Node), or similar — if so, use the project's existing pattern for loading env vars.

### Step 4: Unstage remediated files

After refactoring, make sure the `.env` file (with real secrets) is NOT staged:

```bash
git reset HEAD .env 2>/dev/null  # unstage if accidentally staged
```

Stage the refactored source files (which now reference env vars instead of hardcoded secrets):

```bash
git add <refactored-files>
```

### Step 5: Verify the fix

Re-run Phase 1 scan on the refactored files to confirm the secrets are gone. If any remain, loop back and fix. Do not proceed until the scan is clean.

---

## Phase 4: Report

After remediation (or if the scan was clean from the start), produce a summary:

**Clean scan:**
```
panda-git: Clean scan. 0 secrets found in <N> files scanned. Safe to commit.
```

**After remediation:**
```
panda-git: Found <N> hardcoded secrets. Auto-remediated:

  CRITICAL: sk_live_**** in src/payments.py:42 -> STRIPE_SECRET_KEY
  HIGH:     AIza**** in config/google.ts:18 -> GOOGLE_API_KEY
  MEDIUM:   .env was not in .gitignore -> added

Actions taken:
  - Extracted <N> secrets to .env (gitignored)
  - Created/updated .env.example with placeholder vars
  - Refactored <N> source files to use env var references
  - Updated .gitignore

Verify the app still works with the new env var setup, then commit.
```

**Blocked (auto-fix not possible):**

Some secrets can't be auto-fixed — for example, a private key embedded in a binary file, or a secret in a format the skill can't safely refactor. In these cases:

```
panda-git: BLOCKED. Found secrets that require manual remediation:

  CRITICAL: Private key in assets/cert.pem:1
            -> Move this file outside the repo and reference via path env var

  Action required: Fix the above manually, then run panda-git again.
```

---

## Phase 5: Git History Check (Manual Invocation Only)

When explicitly asked to do a deep scan (e.g., "scan the repo history for secrets"), also check past commits. This is expensive so it only runs on explicit request, not as part of the pre-commit gate.

```bash
git log --all --diff-filter=A --name-only --pretty=format:"%H" -- "*.env" "*.pem" "*.key" "*credentials*" "*secret*"
```

For each historically added sensitive file, check if it's still in the current tree. If it was added and later removed, warn that the secret is still in git history and suggest:

1. Rotate the credential immediately (it's compromised)
2. Use `git filter-repo` or BFG Repo Cleaner to purge from history if needed

---

## Operating Principles

1. **Block first, fix second.** Never let a secret through while figuring out the fix. The commit waits.
2. **Zero false negatives over zero false positives.** It's better to flag something that turns out to be harmless than to miss a real key.
3. **Never log full secrets.** In all output, mask secret values. Show only enough to identify which secret it is (first 8 + last 4 chars).
4. **Env vars are the escape hatch.** The remediation pattern is always: secret goes to gitignored .env, code references the env var.
5. **Existing patterns win.** If the project already uses dotenv, Vault, AWS Secrets Manager, or any other secret management system, match that pattern rather than introducing a new one.
6. **Test files are not exempt.** A real `sk_live_*` key in a test file is just as dangerous as one in production code. Only `sk_test_*` with obviously fake values get a pass.
