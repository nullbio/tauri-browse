---
name: tauri-dogfood
description: Systematically explore and test a Tauri application to find bugs, UX issues, and other problems. Use when asked to "dogfood", "QA", "exploratory test", "find issues", "bug hunt", "test this app", or review the quality of a Tauri application. Produces a structured report with full reproduction evidence -- step-by-step screenshots and detailed repro steps for every issue -- so findings can be handed directly to the responsible teams.
allowed-tools: Bash(tauri-browse:*)
---

# Tauri Dogfood

Systematically explore a Tauri application, find issues, and produce a report with full reproduction evidence for every finding.

## Setup

Only the **Tauri binary** is required. Everything else has sensible defaults -- use them unless the user explicitly provides an override.

| Parameter | Default | Example override |
|-----------|---------|-----------------|
| **Tauri binary** | _(required)_ | `./target/debug/my-app` |
| **Session name** | `dogfood` | `--session my-session` |
| **Output directory** | `./dogfood-output/` | `Output directory: /tmp/qa` |
| **Scope** | Full app | `Focus on the settings page` |
| **Authentication** | None | `Sign in to user@example.com` |

If the user says something like "dogfood my-app", start immediately with defaults. Do not ask clarifying questions unless authentication is mentioned but credentials are missing.

## Workflow

```
1. Initialize    Set up session, output dirs, report file
2. Authenticate  Sign in if needed, save state
3. Orient        Launch app, take initial snapshot
4. Explore       Systematically visit pages and test features
5. Document      Screenshot each issue as found
6. Wrap up       Update summary counts, close session
```

### 1. Initialize

```bash
mkdir -p {OUTPUT_DIR}/screenshots
```

Copy the report template into the output directory and fill in the header fields:

```bash
cp {SKILL_DIR}/templates/dogfood-report-template.md {OUTPUT_DIR}/report.md
```

### 2. Authenticate

If the app requires login:

```bash
tauri-browse launch {BINARY}
tauri-browse wait --load networkidle
tauri-browse snapshot -i
# Identify login form refs, fill credentials
tauri-browse fill @e1 "{EMAIL}"
tauri-browse fill @e2 "{PASSWORD}"
tauri-browse click @e3
tauri-browse wait --load networkidle
```

For OTP/email codes: ask the user, wait for their response, then enter the code.

After successful login, save state for potential reuse:

```bash
tauri-browse state save {OUTPUT_DIR}/auth-state.json
```

### 3. Orient

Take an initial annotated screenshot and snapshot to understand the app structure:

```bash
tauri-browse screenshot --annotate {OUTPUT_DIR}/screenshots/initial.png
tauri-browse snapshot -i
```

Identify the main navigation elements and map out the sections to visit.

### 4. Explore

Read [references/issue-taxonomy.md](references/issue-taxonomy.md) for the full list of what to look for and the exploration checklist.

**Strategy -- work through the app systematically:**

- Start from the main navigation. Visit each top-level section.
- Within each section, test interactive elements: click buttons, fill forms, open dropdowns/modals.
- Check edge cases: empty states, error handling, boundary inputs.
- Try realistic end-to-end workflows (create, edit, delete flows).
- Check the browser console for errors periodically.

**At each page:**

```bash
tauri-browse snapshot -i
tauri-browse screenshot --annotate {OUTPUT_DIR}/screenshots/{page-name}.png
```

Use `tauri-browse eval` to check for console errors:

```bash
tauri-browse eval --stdin <<'EOF'
return JSON.stringify(window.__console_errors__ || [])
EOF
```

Use your judgment on how deep to go. Spend more time on core features and less on peripheral pages. If you find a cluster of issues in one area, investigate deeper.

### 5. Document Issues (Repro-First)

Steps 4 and 5 happen together -- explore and document in a single pass. When you find an issue, stop exploring and document it immediately before moving on. Do not explore the whole app first and document later.

Every issue must be reproducible. When you find something wrong, do not just note it -- prove it with evidence. The goal is that someone reading the report can see exactly what happened and replay it.

**Choose the right level of evidence for the issue:**

#### Interactive / behavioral issues (functional, ux, console errors on action)

These require user interaction to reproduce -- use step-by-step screenshots:

1. **Take a screenshot before the action:**

```bash
tauri-browse screenshot {OUTPUT_DIR}/screenshots/issue-{NNN}-step-1.png
```

2. **Perform the action** (click, fill, etc.) and screenshot the result:

```bash
# Perform action
tauri-browse click @e1
tauri-browse wait 1000
tauri-browse screenshot {OUTPUT_DIR}/screenshots/issue-{NNN}-step-2.png
```

3. **Capture the broken state** with an annotated screenshot:

```bash
tauri-browse screenshot --annotate {OUTPUT_DIR}/screenshots/issue-{NNN}-result.png
```

4. Write numbered repro steps in the report, each referencing its screenshot.

#### Static / visible-on-load issues (typos, placeholder text, clipped text, misalignment)

These are visible without interaction -- a single annotated screenshot is sufficient:

```bash
tauri-browse screenshot --annotate {OUTPUT_DIR}/screenshots/issue-{NNN}.png
```

Write a brief description and reference the screenshot in the report.

---

**For all issues:**

1. **Append to the report immediately.** Do not batch issues for later. Write each one as you find it so nothing is lost if the session is interrupted.

2. **Increment the issue counter** (ISSUE-001, ISSUE-002, ...).

### 6. Wrap Up

Aim to find **5-10 well-documented issues**, then wrap up. Depth of evidence matters more than total count -- 5 issues with full repro beats 20 with vague descriptions.

After exploring:

1. Re-read the report and update the summary severity counts so they match the actual issues. Every `### ISSUE-` block must be reflected in the totals.
2. Close the session:

```bash
tauri-browse close
```

3. Tell the user the report is ready and summarize findings: total issues, breakdown by severity, and the most critical items.

## Guidance

- **Repro is everything.** Every issue needs proof -- but match the evidence to the issue. Interactive bugs need step-by-step screenshots. Static bugs (typos, placeholder text, visual glitches visible on load) only need a single annotated screenshot.
- **Screenshot each step.** Capture the before, the action, and the after -- so someone can see the full sequence.
- **Write repro steps that map to screenshots.** Each numbered step in the report should reference its corresponding screenshot. A reader should be able to follow the steps visually without touching the app.
- **Be thorough but use judgment.** You are not following a test script -- you are exploring like a real user would. If something feels off, investigate.
- **Write findings incrementally.** Append each issue to the report as you discover it. If the session is interrupted, findings are preserved. Never batch all issues for the end.
- **Never delete output files.** Do not `rm` screenshots or the report mid-session. Do not close the session and restart. Work forward, not backward.
- **Never read the target app's source code.** You are testing as a user, not auditing code. Do not read Rust, TypeScript, or config files of the app under test. All findings must come from what you observe in the browser.
- **Test like a user, not a robot.** Try common workflows end-to-end. Click things a real user would click. Enter realistic data.
- **Be efficient with commands.** Batch multiple `tauri-browse` commands in a single shell call when they are independent (e.g., `tauri-browse ... screenshot ... && tauri-browse ... snapshot -i`). Use `tauri-browse scroll down 300` for scrolling.

## References

| Reference | When to Read |
|-----------|--------------|
| [references/issue-taxonomy.md](references/issue-taxonomy.md) | Start of session -- calibrate what to look for, severity levels, exploration checklist |

## Templates

| Template | Purpose |
|----------|---------|
| [templates/dogfood-report-template.md](templates/dogfood-report-template.md) | Copy into output directory as the report file |
