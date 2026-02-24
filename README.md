# tauri-browse

WebDriver CLI for Tauri apps via tauri-driver. Mirrors the [agent-browser](https://github.com/anthropics/agent-browser) API using WebDriver protocol (required for Tauri's WebKitGTK webview on Linux).

## Why not agent-browser?

Tauri on Linux uses WebKitGTK, which exposes a WebDriver interface -- not CDP (Chrome DevTools Protocol). agent-browser uses CDP and cannot connect to WebKitGTK. tauri-browse speaks WebDriver to `tauri-driver`, which wraps WebKitWebDriver, giving you full Tauri IPC access (`window.__TAURI_INTERNALS__`).

## Installation

### From source (recommended)

```bash
pip install .
```

### Development mode

```bash
pip install -e .
```

After installation, `tauri-browse` is available as a system-wide command.

### System dependencies

```bash
# Debian/Ubuntu
sudo apt install webkit2gtk-driver xvfb imagemagick

# Cargo
cargo install tauri-driver --locked
```

## Prerequisites

Before using tauri-browse, you need:

1. **tauri-driver** running (WebDriver server, default port 4444)
2. **Xvfb** running for headless testing (or a real X display)
3. Your Tauri app binary built

A typical setup script runs Xvfb on display `:99`, then starts tauri-driver and a Vite dev server. Example:

```bash
Xvfb :99 -screen 0 1400x900x24 &
DISPLAY=:99 tauri-driver &
```

## Quick start

```bash
# Launch your Tauri app
tauri-browse launch path/to/your-tauri-app

# Take a screenshot to see the current state
tauri-browse screenshot /tmp/screenshot.png

# Get interactive elements with refs
tauri-browse snapshot -i
# Output: @e1 button "Add Project", @e2 input "name", ...

# Interact using refs
tauri-browse click @e1
tauri-browse fill @e2 "my-project"
tauri-browse press Enter

# Re-snapshot after DOM changes (refs are invalidated)
tauri-browse snapshot -i

# Close when done
tauri-browse close
```

## Usage

```
tauri-browse [options] <command> [args]
```

### Global options

| Option | Description | Default |
|---|---|---|
| `--session <name>` | Session name for parallel sessions | `default` |
| `--driver <url>` | WebDriver URL | `http://localhost:4444` |
| `--display <display>` | X display for screenshots | `$DISPLAY` |

### Environment variables

| Variable | Description |
|---|---|
| `TAURI_BROWSE_DRIVER` | WebDriver URL (same as `--driver`) |
| `TAURI_BROWSE_DISPLAY` | X display for screenshots (same as `--display`) |

## Commands

### Navigation

```bash
tauri-browse launch <binary>        # Launch Tauri app via WebDriver
tauri-browse open <url>             # Navigate to URL (aliases: goto, navigate)
tauri-browse close                  # Close session
```

### Snapshots

Get a text representation of interactive elements on the page, each assigned a ref (`@e1`, `@e2`, ...) for interaction.

```bash
tauri-browse snapshot -i            # Interactive elements with refs
tauri-browse snapshot -i -C         # Include cursor-interactive elements
tauri-browse snapshot -i -s "#app"  # Scoped to CSS selector
tauri-browse snapshot -i --json     # Output as JSON
```

### Screenshots

```bash
tauri-browse screenshot [path]          # Capture X display
tauri-browse screenshot --annotate      # Numbered badges on interactive elements
tauri-browse screenshot --full          # Full page (scroll + stitch)
```

The `--annotate` flag overlays numbered badges on interactive elements and prints a legend mapping `[N]` to `@eN`. Refs are cached, so you can interact with elements immediately after.

Screenshots use ImageMagick's `import` command to capture the X display, because WebKitWebDriver's screenshot endpoint does not work reliably under Xvfb.

### Interaction

All interaction commands accept either a ref (`@e1`) or a CSS selector.

```bash
tauri-browse click @e1              # Click element
tauri-browse fill @e2 "text"        # Clear and type
tauri-browse type @e2 "more"        # Type without clearing
tauri-browse select @e3 "option"    # Select dropdown option
tauri-browse check @e4              # Toggle checkbox
tauri-browse press Enter            # Press key (Enter, Tab, Escape, etc.)
tauri-browse scroll down 300        # Scroll (up/down/left/right)
tauri-browse highlight @e1          # Highlight element visually
```

### Semantic find

Find elements by semantic properties and perform an action.

```bash
tauri-browse find text "Sign In" click
tauri-browse find label "Email" fill "user@test.com"
tauri-browse find role button click
tauri-browse find testid "submit-btn" click
tauri-browse find placeholder "Search" type "query"
```

### JavaScript evaluation

```bash
tauri-browse eval "return document.title"

# Complex JS via stdin (avoids shell quoting issues)
tauri-browse eval --stdin <<'EOF'
return Array.from(document.querySelectorAll("a")).map(a => a.href)
EOF
```

### Get information

```bash
tauri-browse get text @e1           # Get element text
tauri-browse get url                # Get current URL
tauri-browse get title              # Get page title
```

### Wait

```bash
tauri-browse wait @e1               # Wait for element to appear
tauri-browse wait 2000              # Wait milliseconds
tauri-browse wait --url "/dashboard" # Wait for URL to contain pattern
tauri-browse wait --load networkidle # Wait for network idle
tauri-browse wait --fn "document.readyState === 'complete'"
```

### Diff

Compare page states for verification and testing.

```bash
# Compare current snapshot to last taken snapshot
tauri-browse diff snapshot

# Compare against a saved baseline file
tauri-browse diff snapshot --baseline before.txt

# Visual pixel diff against a baseline image
tauri-browse diff screenshot --baseline before.png

# Diff two URLs (text comparison)
tauri-browse diff url https://staging.example.com https://prod.example.com

# Diff two URLs (screenshot comparison)
tauri-browse diff url https://staging.example.com https://prod.example.com --screenshot

# Scope diff to a specific element
tauri-browse diff url <url1> <url2> --selector "#main"
```

### Session management

Named sessions allow parallel automation of multiple Tauri instances.

```bash
# Use named sessions
tauri-browse --session app1 launch ./my-app
tauri-browse --session app2 launch ./my-app

# List active sessions
tauri-browse session list

# Each session has independent refs and state
tauri-browse --session app1 snapshot -i
tauri-browse --session app2 snapshot -i
```

### State persistence

Save and restore cookies and localStorage across sessions.

```bash
tauri-browse state save auth.json   # Save current state
tauri-browse state load auth.json   # Restore state
tauri-browse state list             # List saved state files
tauri-browse state clear [name]     # Clear saved state
```

## Ref lifecycle

Refs (`@e1`, `@e2`, etc.) are invalidated when the page changes. Always re-snapshot after:

- Clicking links or buttons that navigate
- Form submissions
- Dynamic content loading (dropdowns, modals)

```bash
tauri-browse click @e5          # Navigates to new page
tauri-browse snapshot -i        # MUST re-snapshot
tauri-browse click @e1          # Use new refs
```

## How it works

tauri-browse communicates with `tauri-driver` over the WebDriver HTTP protocol. tauri-driver wraps WebKitWebDriver, which controls the WebKitGTK webview inside your Tauri app.

```
tauri-browse  --(HTTP/JSON)-->  tauri-driver  --(WebDriver)-->  WebKitWebDriver  -->  Tauri Webview
```

Since this drives the actual Tauri webview (not a regular browser), all Tauri IPC commands work -- you can spawn agents, access the database, invoke Rust commands, etc.

## License

MIT
