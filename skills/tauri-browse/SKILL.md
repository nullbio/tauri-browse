---
name: tauri-browse
description: Browser automation CLI for Tauri apps via WebDriver. Use when the user needs to interact with a Tauri application, including navigating pages, filling forms, clicking buttons, taking screenshots, extracting data, testing Tauri apps, or automating any browser task within a Tauri webview. Triggers include requests to "open the app", "fill out a form", "click a button", "take a screenshot", "scrape data from a page", "test this Tauri app", "login to the app", "automate browser actions", or any task requiring programmatic Tauri webview interaction.
allowed-tools: Bash(tauri-browse:*)
---

# Browser Automation with tauri-browse

## Core Workflow

Every browser automation follows this pattern:

1. **Launch**: `tauri-browse launch <binary>` or `tauri-browse open <url>`
2. **Snapshot**: `tauri-browse snapshot -i` (get element refs like `@e1`, `@e2`)
3. **Interact**: Use refs to click, fill, select
4. **Re-snapshot**: After navigation or DOM changes, get fresh refs

```bash
tauri-browse launch ./path/to/tauri-app
tauri-browse snapshot -i
# Output: @e1 [input type="email"], @e2 [input type="password"], @e3 [button] "Submit"

tauri-browse fill @e1 "user@example.com"
tauri-browse fill @e2 "password123"
tauri-browse click @e3
tauri-browse wait --load networkidle
tauri-browse snapshot -i  # Check result
```

## Command Chaining

Commands can be chained with `&&` in a single shell invocation. The session persists between commands, so chaining is safe and more efficient than separate calls.

```bash
# Chain open + wait + snapshot in one call
tauri-browse open https://example.com && tauri-browse wait --load networkidle && tauri-browse snapshot -i

# Chain multiple interactions
tauri-browse fill @e1 "user@example.com" && tauri-browse fill @e2 "password123" && tauri-browse click @e3

# Navigate and capture
tauri-browse open https://example.com && tauri-browse wait --load networkidle && tauri-browse screenshot page.png
```

**When to chain:** Use `&&` when you don't need to read the output of an intermediate command before proceeding (e.g., open + wait + screenshot). Run commands separately when you need to parse the output first (e.g., snapshot to discover refs, then interact using those refs).

## Essential Commands

```bash
# Navigation
tauri-browse launch <binary>          # Launch Tauri app via WebDriver
tauri-browse open <url>               # Navigate to URL (aliases: goto, navigate)
tauri-browse close                    # Close session
tauri-browse back                     # Navigate back
tauri-browse forward                  # Navigate forward
tauri-browse reload                   # Reload page

# Snapshot
tauri-browse snapshot -i              # Interactive elements with refs (recommended)
tauri-browse snapshot -i -C           # Include cursor-interactive elements
tauri-browse snapshot -i -s "#selector" # Scope to CSS selector
tauri-browse snapshot -i --json       # Output as JSON

# Interaction (use @refs from snapshot)
tauri-browse click @e1                # Click element
tauri-browse dblclick @e1             # Double-click element
tauri-browse hover @e1                # Hover over element
tauri-browse focus @e1                # Focus element
tauri-browse drag @e1 @e2             # Drag from source to destination
tauri-browse fill @e2 "text"          # Clear and type text
tauri-browse type @e2 "text"          # Type without clearing
tauri-browse select @e1 "option"      # Select dropdown option
tauri-browse check @e1                # Check checkbox
tauri-browse uncheck @e1              # Uncheck checkbox (only if checked)
tauri-browse press Enter              # Press key
tauri-browse scroll down 500          # Scroll page
tauri-browse scrollintoview @e1       # Scroll element into view
tauri-browse upload @e1 /path/to/file # Upload file to input
tauri-browse download @e1 --path /tmp # Click and wait for download

# Semantic find
tauri-browse find text "Sign In" click
tauri-browse find label "Email" fill "user@test.com"
tauri-browse find role button click --name "Submit"
tauri-browse find placeholder "Search" type "query"
tauri-browse find testid "submit-btn" click
tauri-browse find alt "Logo" click
tauri-browse find title "Close" click
tauri-browse find first ".card" click
tauri-browse find last ".card" click
tauri-browse find nth 3 ".card" click

# Get information
tauri-browse get text @e1             # Get element text
tauri-browse get html @e1             # Get innerHTML (--outer for outerHTML)
tauri-browse get value @e1            # Get input value
tauri-browse get attr @e1 href        # Get element attribute
tauri-browse get count ".card"        # Count matching elements
tauri-browse get box @e1              # Get bounding rectangle as JSON
tauri-browse get styles @e1 color     # Get computed styles
tauri-browse get url                  # Get current URL
tauri-browse get title                # Get page title

# State checks (prints true/false, exit code 1 for false)
tauri-browse is visible @e1           # Check if element is visible
tauri-browse is enabled @e1           # Check if element is enabled
tauri-browse is checked @e1           # Check if element is checked

# Wait
tauri-browse wait @e1                 # Wait for element
tauri-browse wait --load networkidle  # Wait for network idle
tauri-browse wait --url "/page"       # Wait for URL pattern
tauri-browse wait --text "Welcome"    # Wait for text to appear
tauri-browse wait --fn "document.readyState === 'complete'"
tauri-browse wait 2000                # Wait milliseconds

# Frames
tauri-browse frame @e1                # Switch to iframe
tauri-browse frame main               # Switch back to main frame

# Dialogs
tauri-browse dialog accept            # Accept alert/confirm
tauri-browse dialog accept "input"    # Accept prompt with text
tauri-browse dialog dismiss           # Dismiss dialog
tauri-browse dialog text              # Get dialog text

# Console/Errors
tauri-browse console                  # Show console output
tauri-browse console --level error    # Filter by level
tauri-browse console --clear          # Show and clear
tauri-browse errors                   # Show JS errors
tauri-browse errors --clear           # Show and clear errors

# Capture
tauri-browse screenshot               # Screenshot to temp dir
tauri-browse screenshot --full        # Full page screenshot
tauri-browse screenshot --annotate    # Annotated screenshot with numbered element labels
tauri-browse highlight @e1            # Highlight element visually

# Diff (compare page states)
tauri-browse diff snapshot                          # Compare current vs last snapshot
tauri-browse diff snapshot --baseline before.txt    # Compare current vs saved file
tauri-browse diff screenshot --baseline before.png  # Visual pixel diff
tauri-browse diff url <url1> <url2>                 # Compare two pages

# JavaScript
tauri-browse eval "return document.title"
tauri-browse eval --stdin <<'EOF'
return Array.from(document.querySelectorAll("a")).map(a => a.href)
EOF
```

## Common Patterns

### Form Submission

```bash
tauri-browse launch ./my-tauri-app
tauri-browse snapshot -i
tauri-browse fill @e1 "Jane Doe"
tauri-browse fill @e2 "jane@example.com"
tauri-browse select @e3 "California"
tauri-browse check @e4
tauri-browse click @e5
tauri-browse wait --load networkidle
```

### Authentication with State Persistence

```bash
# Login once and save state
tauri-browse launch ./my-tauri-app
tauri-browse snapshot -i
tauri-browse fill @e1 "$USERNAME"
tauri-browse fill @e2 "$PASSWORD"
tauri-browse click @e3
tauri-browse wait --url "/dashboard"
tauri-browse state save auth.json

# Reuse in future sessions
tauri-browse state load auth.json
tauri-browse open https://app.example.com/dashboard
```

### Data Extraction

```bash
tauri-browse launch ./my-tauri-app
tauri-browse snapshot -i
tauri-browse get text @e5           # Get specific element text
tauri-browse get text body > page.txt  # Get all page text

# JSON output for parsing
tauri-browse snapshot -i --json
```

### Parallel Sessions

```bash
tauri-browse --session app1 launch ./my-app
tauri-browse --session app2 launch ./my-app

tauri-browse --session app1 snapshot -i
tauri-browse --session app2 snapshot -i

tauri-browse session list
```

## Diffing (Verifying Changes)

Use `diff snapshot` after performing an action to verify it had the intended effect. This compares the current accessibility tree against the last snapshot taken in the session.

```bash
# Typical workflow: snapshot -> action -> diff
tauri-browse snapshot -i          # Take baseline snapshot
tauri-browse click @e2            # Perform action
tauri-browse diff snapshot        # See what changed (auto-compares to last snapshot)
```

For visual regression testing:

```bash
# Save a baseline screenshot, then compare later
tauri-browse screenshot baseline.png
# ... changes are made ...
tauri-browse diff screenshot --baseline baseline.png
```

`diff snapshot` output uses `+` for additions and `-` for removals, similar to git diff. `diff screenshot` produces a diff image with changed pixels highlighted in red, plus a mismatch percentage.

## Timeouts and Slow Pages

When dealing with slow-loading content, use explicit waits:

```bash
# Wait for network activity to settle
tauri-browse wait --load networkidle

# Wait for a specific element to appear
tauri-browse wait "#content"
tauri-browse wait @e1

# Wait for a URL pattern (useful after redirects)
tauri-browse wait --url "/dashboard"

# Wait for a JavaScript condition
tauri-browse wait --fn "document.readyState === 'complete'"

# Wait a fixed duration (milliseconds) as a last resort
tauri-browse wait 5000
```

## Session Management and Cleanup

When running multiple automations concurrently, always use named sessions to avoid conflicts:

```bash
# Each automation gets its own isolated session
tauri-browse --session agent1 launch ./my-app
tauri-browse --session agent2 launch ./my-app

# Check active sessions
tauri-browse session list
```

Always close your session when done:

```bash
tauri-browse close                    # Close default session
tauri-browse --session agent1 close   # Close specific session
```

## Ref Lifecycle (Important)

Refs (`@e1`, `@e2`, etc.) are invalidated when the page changes. Always re-snapshot after:

- Clicking links or buttons that navigate
- Form submissions
- Dynamic content loading (dropdowns, modals)

```bash
tauri-browse click @e5              # Navigates to new page
tauri-browse snapshot -i            # MUST re-snapshot
tauri-browse click @e1              # Use new refs
```

## Annotated Screenshots (Vision Mode)

Use `--annotate` to take a screenshot with numbered labels overlaid on interactive elements. Each label `[N]` maps to ref `@eN`. This also caches refs, so you can interact with elements immediately without a separate snapshot.

```bash
tauri-browse screenshot --annotate
# Output includes the image path and a legend:
#   [1] @e1 button "Submit"
#   [2] @e2 link "Home"
#   [3] @e3 textbox "Email"
tauri-browse click @e2              # Click using ref from annotated screenshot
```

Use annotated screenshots when:
- The page has unlabeled icon buttons or visual-only elements
- You need to verify visual layout or styling
- Canvas or chart elements are present (invisible to text snapshots)
- You need spatial reasoning about element positions

## Semantic Locators (Alternative to Refs)

When refs are unavailable or unreliable, use semantic locators:

```bash
tauri-browse find text "Sign In" click
tauri-browse find label "Email" fill "user@test.com"
tauri-browse find role button click --name "Submit"
tauri-browse find placeholder "Search" type "query"
tauri-browse find testid "submit-btn" click
```

## JavaScript Evaluation (eval)

Use `eval` to run JavaScript in the browser context. Use `--stdin` to avoid shell quoting issues.

```bash
# Simple expressions work with regular quoting
tauri-browse eval "return document.title"

# Complex JS: use --stdin with heredoc (RECOMMENDED)
tauri-browse eval --stdin <<'EVALEOF'
return JSON.stringify(
  Array.from(document.querySelectorAll("img"))
    .filter(i => !i.alt)
    .map(i => ({ src: i.src.split("/").pop(), width: i.width }))
)
EVALEOF
```

**Why this matters:** When the shell processes your command, inner double quotes, `!` characters (history expansion), backticks, and `$()` can all corrupt the JavaScript before it reaches tauri-browse. The `--stdin` flag bypasses shell interpretation entirely.

**Rules of thumb:**
- Single-line, no nested quotes -> regular `eval "expression"` is fine
- Nested quotes, arrow functions, template literals, or multiline -> use `eval --stdin <<'EVALEOF'`

## Configuration File

Create `tauri-browse.json` in the project root for persistent settings:

```json
{
  "driver": "http://localhost:4444",
  "display": ":99",
  "session": "default",
  "json": false,
  "full": false,
  "annotate": false,
  "debug": false,
  "timeout": 10
}
```

Priority (lowest to highest): `~/.tauri-browse/config.json` < `./tauri-browse.json` < env vars < CLI flags. Use `--config <path>` or `TAURI_BROWSE_CONFIG` env var for a custom config file. All CLI options map to camelCase keys. Boolean flags accept `true`/`false` values (e.g., `--json false` overrides config).

## Tauri IPC Access

Since tauri-browse drives the actual Tauri webview (not a regular browser), all Tauri IPC commands work. You can invoke Rust commands via JavaScript:

```bash
tauri-browse eval --stdin <<'EOF'
return window.__TAURI_INTERNALS__.invoke("my_command", { arg: "value" })
EOF
```

## Deep-Dive Documentation

| Reference | When to Use |
|-----------|-------------|
| [references/commands.md](references/commands.md) | Full command reference with all options |
| [references/snapshot-refs.md](references/snapshot-refs.md) | Ref lifecycle, invalidation rules, troubleshooting |
| [references/session-management.md](references/session-management.md) | Parallel sessions, state persistence |
| [references/authentication.md](references/authentication.md) | Login flows, state reuse |

## Ready-to-Use Templates

| Template | Description |
|----------|-------------|
| [templates/form-automation.sh](templates/form-automation.sh) | Form filling with validation |
| [templates/authenticated-session.sh](templates/authenticated-session.sh) | Login once, reuse state |
| [templates/capture-workflow.sh](templates/capture-workflow.sh) | Content extraction with screenshots |

```bash
./templates/form-automation.sh /path/to/tauri-app
./templates/authenticated-session.sh /path/to/tauri-app
./templates/capture-workflow.sh /path/to/tauri-app ./output
```
