# Session Management

Multiple isolated browser sessions with state persistence.

**Related**: [authentication.md](authentication.md) for login patterns, [SKILL.md](../SKILL.md) for quick start.

## Contents

- [Named Sessions](#named-sessions)
- [Session Isolation Properties](#session-isolation-properties)
- [Session State Persistence](#session-state-persistence)
- [Common Patterns](#common-patterns)
- [Default Session](#default-session)
- [Session Cleanup](#session-cleanup)
- [Best Practices](#best-practices)

## Named Sessions

Use `--session` flag to isolate browser contexts:

```bash
# Session 1: Authentication flow
tauri-browse --session auth launch ./my-app

# Session 2: Separate instance
tauri-browse --session testing launch ./my-app

# Commands are isolated by session
tauri-browse --session auth fill @e1 "user@example.com"
tauri-browse --session testing get text body
```

## Session Isolation Properties

Each session has independent:
- Cookies
- LocalStorage / SessionStorage
- Browsing history
- Element refs

## Session State Persistence

### Save Session State

```bash
# Save cookies, storage, and auth state
tauri-browse state save /path/to/auth-state.json
```

### Load Session State

```bash
# Restore saved state
tauri-browse state load /path/to/auth-state.json

# Continue with authenticated session
tauri-browse open https://app.example.com/dashboard
```

### State File Contents

```json
{
  "cookies": [...],
  "localStorage": {...}
}
```

## Common Patterns

### Authenticated Session Reuse

```bash
#!/bin/bash
# Save login state once, reuse many times

STATE_FILE="/tmp/auth-state.json"

# Check if we have saved state
if [[ -f "$STATE_FILE" ]]; then
    tauri-browse state load "$STATE_FILE"
    tauri-browse open https://app.example.com/dashboard
else
    # Perform login
    tauri-browse launch ./my-app
    tauri-browse snapshot -i
    tauri-browse fill @e1 "$USERNAME"
    tauri-browse fill @e2 "$PASSWORD"
    tauri-browse click @e3
    tauri-browse wait --load networkidle

    # Save for future use
    tauri-browse state save "$STATE_FILE"
fi
```

### A/B Testing Sessions

```bash
# Test different configurations
tauri-browse --session variant-a launch ./my-app
tauri-browse --session variant-b launch ./my-app

# Compare
tauri-browse --session variant-a screenshot /tmp/variant-a.png
tauri-browse --session variant-b screenshot /tmp/variant-b.png
```

## Default Session

When `--session` is omitted, commands use the default session:

```bash
# These use the same default session
tauri-browse launch ./my-app
tauri-browse snapshot -i
tauri-browse close  # Closes default session
```

## Session Cleanup

```bash
# Close specific session
tauri-browse --session auth close

# List active sessions
tauri-browse session list
```

## Best Practices

### 1. Name Sessions Semantically

```bash
# GOOD: Clear purpose
tauri-browse --session login-flow launch ./my-app
tauri-browse --session data-export launch ./my-app

# AVOID: Generic names
tauri-browse --session s1 launch ./my-app
```

### 2. Always Clean Up

```bash
# Close sessions when done
tauri-browse --session auth close
tauri-browse --session testing close
```

### 3. Handle State Files Securely

```bash
# Don't commit state files (contain auth tokens!)
echo "*.auth-state.json" >> .gitignore

# Delete after use
rm /tmp/auth-state.json
```

### 4. Timeout Long Sessions

```bash
# Set timeout for automated scripts
timeout 60 tauri-browse --session long-task get text body
```
