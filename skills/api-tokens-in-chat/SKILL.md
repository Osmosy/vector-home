---
name: api-tokens-in-chat
description: Use when the user pastes a real API key, token, password, or credential into the chat — for GitHub PAT, OpenAI/Anthropic keys, AWS access keys, OAuth tokens, or any secret that looks like `ghp_*`, `sk-*`, `AKIA*`, `xox[abp]-*`, `eyJ*` (JWT), or any string with high entropy that matches a known provider format. Trigger on "проверь токены", "вот мой ключ", "use this token", or any inline credential.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Security, Secrets, Tokens, API-Keys, Hermes, AGENTS.md, Best-Practices]
    related_skills: [hermes-tooling-quirks]
---

# API Tokens in Chat — Incident Response

When the user pastes a real API token / key / credential into chat, treat it as a security incident. Don't proceed with normal work until the credential is rotated or the user explicitly accepts the risk.

## When to Trigger

User message contains any of:
- GitHub PAT: `ghp_*`, `gho_*`, `ghu_*`, `ghs_*`, `ghr_*`
- OpenAI / Anthropic / OpenRouter: `sk-*`, `sk-or-*`, `sk-ant-*`
- AWS access key: `AKIA*`, `ASIA*`
- Slack: `xox[abp]-*`
- Google API key: `AIza*`
- JWT: `eyJ*`
- Bearer tokens with high entropy (≥40 base64url chars)
- Any "проверь токены" / "use this key" / "вот мой ключ" / "сделай push с этим"

## Required Response (in order)

### 1. STOP and WARN (before any action, including "go")

Issue a clear warning in the FIRST assistant turn after the token appears, BEFORE any classification or use. This warning is mandatory even if the user has given "go" / "делай сам" / "поехали" — the user's existing directives do not override the security incident response.

```
СТОП — ты вставил реальный [тип токена] в чат.
Чат-сессии не считаются секретным хранилищем. Токен уже
потенциально доступен провайдеру чата, логам, бэкапам.
```

After the warning, STOP and wait for explicit user response. Do not proceed to Step 2 (classification) in the same turn — the user must acknowledge the incident before the token is touched again. Captured 2026-06-20: user said "проверь токены / [token] / еще токен" then later "go с дефолтами" — agent proceeded straight to execute_code with the token without an intermediate STOP confirmation. The user's prior "go" does NOT constitute consent to handle a leaked token. A separate acknowledgement is required.

Cite AGENTS.md §2 ("реальные API-ключи НИКОГДА в `curl -H
Authorization: Bearer *** в shell") to anchor the rule.

Only after the user explicitly acknowledges ("ревокай сам",
"делай что сказал", or a clear "продолжай с токеном X для Y")
do you proceed to Step 2.

### 2. CLASSIFY the token (before using it)

Run a MINIMAL, READ-ONLY validation via Python `urllib.request.Request(headers={"Authorization": f"Bearer {token}"})` — NOT `curl -H` in shell (the latter pollutes bash_history with the secret).

For GitHub PATs specifically:
```python
import urllib.request, urllib.error
req = urllib.request.Request(
    "https://api.github.com/user",
    headers={"Authorization": "token " + TOKEN, "Accept": "application/vnd.github+json"}
)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        import json; data = json.loads(r.read().decode())
    print("login:", data.get("login"), "id:", data.get("id"))
except urllib.error.HTTPError as e:
    print("status:", e.code, "reason:", e.reason)
```

Result tells you:
- 200 + login → token is valid; proceed with caveat
- 401 → token is dead; don't bother using
- 403 / 404 → token valid but scope insufficient; ask user
- Network error → retry once; otherwise report and stop

### 3. ASK before using the token for actions with side effects

Even after a "go", do NOT immediately push / post / delete. Confirm:
- Action is what the user wants (push to which branch? delete which repo?)
- Token has the right scope for the action
- User accepts that the token will be logged in this session

If user says "делай всё сам", proceed with the safety rules below.

### 4. SAFETY RULES when using a chat-pasted token

**Mandatory:**

1. **Load token from a file, not from a shell variable.** Reason: shell variables get logged to `.bash_history`, scrollback, core dumps. Use `write_file(path="/tmp/<name>", content=token)` first, then read with `open(path).read()` inside `execute_code`. Never `export TOKEN=...` in terminal.

2. **Never use `curl -H "Authorization: token $TOKEN"` in shell.** Use Python `urllib.request.Request(headers={...})` or load the token into git credential store via Python subprocess (not shell).

3. **Use isolated HOME for git credential.** When configuring `git push`, write credential file in a `tempfile.mkdtemp()` dir, set `HOME=tmp_home` in the subprocess env, then `shutil.rmtree` after. Don't pollute `~/.git-credentials`.

4. **Don't print the token in any log line.** Even partial. Even in error messages. Even for "just to confirm I have the right one". Mask in every print: use `***[:8]+"..."+***[-4:]` style only when strictly necessary; usually print nothing.

5. **Don't write the token into a `write_file` source that you later `read_file`.** Reason: tool input/output may be persisted. If you must write a Python script that uses the token, write the script with the token load via `open(<temp>).read()`, and clean up the temp file immediately after use.

6. **Cleanup after use:**
   ```python
   with open(cred_file, "wb") as f:
       f.write(os.urandom(2048))  # overwrite with random bytes
   os.unlink(cred_file)
   ```
   Then `shutil.rmtree(tmp_home)` and `del token_var` in Python local scope.

### 5. TRY TO REVOKE the token via API (best-effort)

For GitHub PATs:
```python
req = urllib.request.Request(
    "https://api.github.com/authorizations",
    headers={"Authorization": "token " + token_value,
             "Accept": "application/vnd.github+json"}
)
# List authorizations; for each, DELETE /authorizations/{id}
```

Caveats:
- The `/authorizations` endpoint requires the token itself AND classic PAT scopes (`admin:oauth` or `manage_tokens`). Fine-grained PATs CANNOT be revoked via API — must be done in https://github.com/settings/tokens.
- If the cleanup overwrites the token file BEFORE the revoke call, you cannot revoke — you have to tell the user to do it manually.

**Always tell the user which tokens must be manually revoked and where.** Don't assume the API revoke succeeded.

### 6. DOCUMENT the incident

Update memory with one declarative fact per session:
- "Session YYYY-MM-DD: user pasted N real [type] tokens in chat. Used N for [action]. R-voke status: [API done / user must do manually]."
- This is procedural lesson, not a per-task log. Save as a SKILL (this one) and reference it from memory.

### 7. RECOMMEND immediate rotation

End every incident response with:
```
Рекомендую ревокнуть токен вручную:
1. https://github.com/settings/tokens (или провайдер-специфичный URL)
2. Найти PAT по [note if any] или по последнему использованию
3. Delete → подтвердить
4. Выпустить новый fine-grained токен с минимальными scope
5. Сохранять только в ~/.git-credentials (chmod 600) или через gh auth login
```

## Common Pitfalls

1. **Proceeding silently.** User pastes token → agent uses it without warning. Worst case: token leaks to chat logs, tool I/O, browser history if any web preview happens.

2. **Using `*** try `print("TOKEN=*** TOKEN)` "just to verify it's loaded".** Don't. The print goes to terminal where the user sees it AND to any captured output (tirith, log files, browser preview).

3. **`curl -H "Authorization: token $TOKEN"`** — even `set +o history` doesn't help (history is one of MANY leakage paths; scrollback, journald if launched under systemd, etc.).

4. **`export TOKEN=*** in `terminal()` for subprocess inheritance.** Same problem. Use Python with explicit env dict.

5. **API revoke as cleanup.** Works for some classic PATs but NOT for fine-grained PATs. Always recommend manual revoke at https://github.com/settings/tokens.

6. **Assuming the token is unique to one account.** A token pasted in chat might belong to a CI/CD service account, a personal account, or a shared account. Confirm by `/user` lookup. Don't assume the user's "main" account.

7. **Pasting the token in a `write_file` script and then running it via `subprocess.run([sys.executable, script])`.** The token is now in TWO files (the script + the temp cred). Cleanup must cover both.

8. **Trying to revoke AFTER cleanup.** If you deleted the temp file with the token, you can't make an authenticated API call to revoke. Decide revoke-vs-cleanup order BEFORE starting.

9. **Skipping the warning because "the user already knows what they're doing".** Maybe yes, maybe no. The warning is cheap; a leaked token is not.

10. **Saving the token in memory ("user's GitHub PAT is X").** Memory is durable across sessions; saving a real token there guarantees long-term exposure. Save only the FACT that a token was used (with date and scope summary), never the token itself.

11. **Mask pattern `TOKEN=*** in source breaks Python syntax.** When you write a script that uses a secret and try to mask the variable assignment inline (e.g. `TOKEN=*** ` → `TOKEN=***`), the replacement eats the closing quote and the parser raises `SyntaxError: unterminated string literal`. Three failures in a row on 2026-06-20 trying to mask `TOKEN=*** → `TOKEN=***`. **Fix:** never put the literal in the script at all — load via `with open("/tmp/<name>") as f: token_value = f.read().strip()`. Don't edit the variable name with `***` masking. Also applies to masking in `write_file` content; see `devops/hermes-tooling-quirks` pitfall on the same topic.

12. **`write_file` can append padding to short Python scripts, breaking line numbers.** Observed 2026-06-20: a 1.6 KB Python script written via `write_file` ended up at 2 KB on disk. If you rely on line numbers in subsequent `read_file` errors, they may be off. Always `read_file` the file after `write_file` to confirm exact contents; for sensitive scripts, run them via `subprocess.run([sys.executable, "<path>"])` rather than expecting the sandbox to interpret the bytes you sent. See `devops/hermes-tooling-quirks` for the canonical pitfall.

13. **Don't auto-act on informational context.** When the user pastes a GitHub settings dump (list of their PATs, OAuth apps, etc.) and says "это просто информация" / "just showed for context" — don't try to auto-revoke, auto-rotate, or propose API calls. They are showing you state, not asking for action. Treat it as a read-only signal. Captured 2026-06-20 when the user shared their `Personal access tokens (classic)` page after the push incident — I almost proposed "let me audit-log the Osmosis token" before they explicitly told me to stop.

## Verification Checklist

- [ ] Warning issued in first turn after token appeared
- [ ] Token classified via Python urllib (not curl -H)
- [ ] User confirmed action with side effects
- [ ] Token loaded from temp file, not shell variable
- [ ] Credential store in isolated HOME (tempfile.mkdtemp)
- [ ] Token file overwritten with random bytes + unlinked after use
- [ ] API revoke attempted (or explicitly noted as not possible)
- [ ] Manual revoke instructions given to user
- [ ] Incident documented in memory (without the token itself)
- [ ] This skill loaded on future token-in-chat events (via triggers field in frontmatter)

## Related Skills

- `hermes-tooling-quirks` — general tooling patterns and pitfalls in this user's Hermes setup
- `verification-before-completion` (superpowers) — applies to actions that touch shared state
