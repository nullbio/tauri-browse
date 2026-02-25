# Command Reference

Complete reference for all tauri-browse commands. For quick start and common patterns, see SKILL.md.

## Navigation

```bash
tauri-browse launch <binary>     # Launch Tauri app via WebDriver
tauri-browse open <url>          # Navigate to URL (aliases: goto, navigate)
tauri-browse close               # Close session (aliases: quit, exit)
```

## Snapshot (page analysis)

```bash
tauri-browse snapshot            # Full accessibility tree
tauri-browse snapshot -i         # Interactive elements only (recommended)
tauri-browse snapshot -i -C      # Include cursor-interactive elements
tauri-browse snapshot -i -s "#main"  # Scope to CSS selector
tauri-browse snapshot -i --json  # Output as JSON
```

## Interactions (use @refs from snapshot)

```bash
tauri-browse click @e1           # Click
tauri-browse fill @e2 "text"     # Clear and type
tauri-browse type @e2 "text"     # Type without clearing
tauri-browse press Enter         # Press key
tauri-browse press Control+a     # Key combination
tauri-browse check @e1           # Check checkbox
tauri-browse select @e1 "value"  # Select dropdown option
tauri-browse scroll down 500     # Scroll page (default: down 300px)
tauri-browse highlight @e1       # Highlight element visually
```

## Get Information

```bash
tauri-browse get text @e1        # Get element text
tauri-browse get url             # Get current URL
tauri-browse get title           # Get page title
```

## Screenshots

```bash
tauri-browse screenshot          # Save to temporary directory
tauri-browse screenshot path.png # Save to specific path
tauri-browse screenshot --full   # Full page (scroll + stitch)
tauri-browse screenshot --annotate  # Numbered badges on interactive elements
```

The `--annotate` flag overlays numbered badges on interactive elements and prints a legend mapping `[N]` to `@eN`. Refs are cached, so you can interact with elements immediately after.

Screenshots use ImageMagick's `import` command to capture the X display, because WebKitWebDriver's screenshot endpoint does not work reliably under Xvfb.

## Semantic Locators (alternative to refs)

```bash
tauri-browse find role button click --name "Submit"
tauri-browse find text "Sign In" click
tauri-browse find text "Sign In" click --exact      # Exact match only
tauri-browse find label "Email" fill "user@test.com"
tauri-browse find placeholder "Search" type "query"
tauri-browse find testid "submit-btn" click
```

Both explicit `role="..."` attributes and implicit roles (e.g. `<button>` for `role=button`) are matched.

## Wait

```bash
tauri-browse wait @e1                     # Wait for element
tauri-browse wait 2000                    # Wait milliseconds
tauri-browse wait --url "/dashboard"      # Wait for URL to contain pattern
tauri-browse wait --load networkidle      # Wait for network idle
tauri-browse wait --fn "window.ready"     # Wait for JS condition
```

## Diff (compare page states)

```bash
tauri-browse diff snapshot                          # Compare current vs last snapshot
tauri-browse diff snapshot --baseline before.txt    # Compare against saved file
tauri-browse diff screenshot --baseline before.png  # Visual pixel diff
tauri-browse diff url <url1> <url2>                 # Compare two URLs (text)
tauri-browse diff url <url1> <url2> --screenshot    # Compare two URLs (visual)
tauri-browse diff url <url1> <url2> --selector "#main"  # Scope to element
```

## JavaScript

```bash
tauri-browse eval "return document.title"     # Simple expressions
tauri-browse eval --stdin                     # Read script from stdin
```

Use `--stdin` with heredoc for reliable execution of complex scripts:

```bash
tauri-browse eval --stdin <<'EOF'
return Array.from(document.querySelectorAll('a')).map(a => a.href)
EOF
```

## Session Management

```bash
tauri-browse --session <name> ...    # Isolated session
tauri-browse session list            # List active sessions
```

## State Persistence

```bash
tauri-browse state save auth.json    # Save cookies, storage state
tauri-browse state load auth.json    # Restore saved state
tauri-browse state list              # List saved state files
tauri-browse state clear [name]      # Clear saved state
```

## Global Options

```bash
tauri-browse --session <name> ...    # Isolated session name
tauri-browse --driver <url> ...      # WebDriver URL (default: http://localhost:4444)
tauri-browse --display <display> ... # X display for screenshots (auto-detected from Xvfb)
tauri-browse --config <path> ...     # Explicit config file path
tauri-browse --json ...              # JSON output for snapshots
tauri-browse --full ...              # Full page screenshots
tauri-browse --annotate ...          # Annotated screenshots
tauri-browse --debug ...             # Verbose output
tauri-browse --timeout <secs> ...    # Request timeout in seconds (default: 10)
tauri-browse --download-path <p> ... # Default download directory
tauri-browse --help                  # Show help
```

Boolean flags accept an optional `true`/`false` value (e.g. `--json false` to override a config default).

## Environment Variables

```bash
TAURI_BROWSE_CONFIG="path/to/config.json"    # Explicit config file
TAURI_BROWSE_DRIVER="http://localhost:4444"   # WebDriver URL
TAURI_BROWSE_DISPLAY=":99"                   # X display for screenshots
TAURI_BROWSE_SESSION="mysession"             # Default session name
TAURI_BROWSE_JSON="true"                     # Default to JSON output
TAURI_BROWSE_FULL="true"                     # Default to full screenshots
TAURI_BROWSE_ANNOTATE="true"                 # Default to annotated screenshots
TAURI_BROWSE_DEBUG="true"                    # Verbose output
TAURI_BROWSE_TIMEOUT="10"                    # Request timeout in seconds
TAURI_BROWSE_DOWNLOAD_PATH="/tmp/downloads"  # Default download directory
```

## Display Auto-Detection

tauri-browse automatically detects a running Xvfb process and uses its display for screenshots. The resolution order:

1. `--display` CLI flag
2. `TAURI_BROWSE_DISPLAY` env var
3. `display` in config file
4. Running Xvfb process (auto-detected via `pgrep`)
5. `DISPLAY` env var
