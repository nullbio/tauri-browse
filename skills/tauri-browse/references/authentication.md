# Authentication Patterns

Login flows, session persistence, and authenticated browsing for Tauri apps.

**Related**: [session-management.md](session-management.md) for state persistence details, [SKILL.md](../SKILL.md) for quick start.

## Contents

- [Basic Login Flow](#basic-login-flow)
- [Saving Authentication State](#saving-authentication-state)
- [Restoring Authentication](#restoring-authentication)
- [OAuth / SSO Flows](#oauth--sso-flows)
- [Two-Factor Authentication](#two-factor-authentication)
- [Token Refresh Handling](#token-refresh-handling)
- [Security Best Practices](#security-best-practices)

## Basic Login Flow

```bash
# Launch the Tauri app
tauri-browse launch ./my-app
tauri-browse wait --load networkidle

# Get form elements
tauri-browse snapshot -i
# Output: @e1 [input type="email"], @e2 [input type="password"], @e3 [button] "Sign In"

# Fill credentials
tauri-browse fill @e1 "user@example.com"
tauri-browse fill @e2 "password123"

# Submit
tauri-browse click @e3
tauri-browse wait --load networkidle

# Verify login succeeded
tauri-browse get url  # Should be dashboard, not login
```

## Saving Authentication State

After logging in, save state for reuse:

```bash
# Login first (see above)
tauri-browse launch ./my-app
tauri-browse snapshot -i
tauri-browse fill @e1 "user@example.com"
tauri-browse fill @e2 "password123"
tauri-browse click @e3
tauri-browse wait --url "/dashboard"

# Save authenticated state
tauri-browse state save ./auth-state.json
```

## Restoring Authentication

Skip login by loading saved state:

```bash
# Load saved auth state
tauri-browse state load ./auth-state.json

# Navigate directly to protected page
tauri-browse open https://app.example.com/dashboard

# Verify authenticated
tauri-browse snapshot -i
```

## OAuth / SSO Flows

For OAuth redirects within the Tauri webview:

```bash
# Start OAuth flow
tauri-browse launch ./my-app
tauri-browse snapshot -i
tauri-browse click @e1  # "Sign in with Google" button

# Handle redirects
tauri-browse wait 2000
tauri-browse snapshot -i

# Fill OAuth provider credentials
tauri-browse fill @e1 "user@gmail.com"
tauri-browse click @e2  # Next button
tauri-browse wait 2000
tauri-browse snapshot -i
tauri-browse fill @e3 "password"
tauri-browse click @e4  # Sign in

# Wait for redirect back
tauri-browse wait --url "/dashboard"
tauri-browse state save ./oauth-state.json
```

## Two-Factor Authentication

Handle 2FA with manual intervention:

```bash
# Login with credentials
tauri-browse launch ./my-app
tauri-browse snapshot -i
tauri-browse fill @e1 "user@example.com"
tauri-browse fill @e2 "password123"
tauri-browse click @e3

# Wait for user to complete 2FA
echo "Complete 2FA in the app window..."
tauri-browse wait --url "/dashboard"

# Save state after 2FA
tauri-browse state save ./2fa-state.json
```

## Token Refresh Handling

For sessions with expiring tokens:

```bash
#!/bin/bash
# Wrapper that handles token refresh

STATE_FILE="./auth-state.json"

# Try loading existing state
if [[ -f "$STATE_FILE" ]]; then
    tauri-browse state load "$STATE_FILE"
    tauri-browse open https://app.example.com/dashboard

    # Check if session is still valid
    URL=$(tauri-browse get url)
    if [[ "$URL" == *"/login"* ]]; then
        echo "Session expired, re-authenticating..."
        # Perform fresh login
        tauri-browse snapshot -i
        tauri-browse fill @e1 "$USERNAME"
        tauri-browse fill @e2 "$PASSWORD"
        tauri-browse click @e3
        tauri-browse wait --url "/dashboard"
        tauri-browse state save "$STATE_FILE"
    fi
else
    # First-time login
    tauri-browse launch ./my-app
    # ... login flow ...
fi
```

## Security Best Practices

1. **Never commit state files** - They contain session tokens
   ```bash
   echo "*.auth-state.json" >> .gitignore
   ```

2. **Use environment variables for credentials**
   ```bash
   tauri-browse fill @e1 "$APP_USERNAME"
   tauri-browse fill @e2 "$APP_PASSWORD"
   ```

3. **Clean up after automation**
   ```bash
   rm -f ./auth-state.json
   ```

4. **Use short-lived sessions for CI/CD**
   ```bash
   # Don't persist state in CI
   tauri-browse launch ./my-app
   # ... login and perform actions ...
   tauri-browse close  # Session ends, nothing persisted
   ```
