#!/usr/bin/env python3
"""
tauri-browse - WebDriver CLI for Tauri apps via tauri-driver.

Mirrors the agent-browser API using WebDriver protocol (required for
Tauri's WebKitGTK webview on Linux).

Usage:
    tauri-browse [options] <command> [args]

Global options:
    --session <name>    Session name (default: "default")
    --driver <url>      WebDriver URL (default: http://localhost:4444)
    --display <display> X display for screenshots

Commands:
    launch <binary>             Launch Tauri app via WebDriver
    open <url>                  Navigate to URL (aliases: goto, navigate)
    close                       Close session

    snapshot -i                 Interactive elements with @refs
    snapshot -i -C              Include cursor-interactive elements
    snapshot -i -s <selector>   Scoped to CSS selector
    snapshot -i --json          Output as JSON

    screenshot [path]           Screenshot (X display capture)
    screenshot --annotate       Annotated screenshot with numbered badges
    screenshot --full           Full page screenshot (scroll + stitch)

    click <@ref|sel>            Click element
    fill <@ref|sel> <text>      Clear and type into element
    type <@ref|sel> <text>      Type without clearing
    select <@ref|sel> <val>     Select dropdown option
    check <@ref|sel>            Toggle checkbox
    press <key>                 Press keyboard key
    scroll <dir> <amount>       Scroll (up/down/left/right)
    highlight <@ref|sel>        Highlight element visually

    find text <text> <action>   Find by text content, then act
    find label <text> <action>  Find by aria-label, then act
    find role <role> <action>   Find by role attribute, then act
    find testid <id> <action>   Find by data-testid, then act
    find placeholder <t> <act>  Find by placeholder, then act

    eval <js>                   Execute JS in webview
    eval --stdin                Read JS from stdin

    get text <@ref|sel>         Get element text
    get url                     Get current URL
    get title                   Get page title

    wait <@ref|sel>             Wait for element
    wait <ms>                   Wait milliseconds
    wait --url <pattern>        Wait for URL to contain pattern
    wait --load networkidle     Wait for network idle
    wait --fn <js>              Wait for JS condition to be truthy

    diff snapshot               Compare with last snapshot
    diff snapshot --baseline f  Compare with saved snapshot file
    diff screenshot --baseline  Visual pixel diff against baseline image
    diff url <u1> <u2>          Diff two URLs (text or --screenshot)

    session list                List active sessions
    state save <file>           Save cookies + localStorage
    state load <file>           Restore cookies + localStorage
    state list                  List saved state files
    state clear [name]          Clear saved state

Environment variables:
    TAURI_BROWSE_DRIVER         WebDriver URL (default: http://localhost:4444)
    TAURI_BROWSE_DISPLAY        X display for screenshots
"""

import sys
import os
import json
import base64
import urllib.request
import urllib.error
import time
import tempfile
import subprocess
from pathlib import Path

VERSION = "0.1.0"
DEFAULT_DRIVER = "http://localhost:4444"
REQUEST_TIMEOUT = 10
CONFIG_DIR = Path.home() / ".tauri-browse"
SESSIONS_DIR = CONFIG_DIR / "sessions"
STATES_DIR = CONFIG_DIR / "states"

SPECIAL_KEYS = {
    "enter": "\uE007", "return": "\uE007",
    "tab": "\uE004",
    "escape": "\uE00C", "esc": "\uE00C",
    "backspace": "\uE003",
    "delete": "\uE017",
    "space": "\uE00D",
    "arrowup": "\uE013", "up": "\uE013",
    "arrowdown": "\uE015", "down": "\uE015",
    "arrowleft": "\uE012", "left": "\uE012",
    "arrowright": "\uE014", "right": "\uE014",
    "home": "\uE011",
    "end": "\uE010",
    "pageup": "\uE00E",
    "pagedown": "\uE00F",
}

INTERACTIVE_QUERY = (
    'a, button, input, select, textarea, [role="button"], [role="link"], '
    '[role="tab"], [role="checkbox"], [role="radio"], [role="menuitem"], '
    '[tabindex], [onclick]'
)

CURSOR_INTERACTIVE_QUERY = (
    INTERACTIVE_QUERY + ', [style*="cursor"], [class]'
)

SNAPSHOT_JS = """
const scope = arguments[0] ? document.querySelector(arguments[0]) : document;
if (!scope) return [];
const query = arguments[1];
const checkCursor = arguments[2];
const elements = [];

function generateSelector(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.getAttribute('data-testid'))
        return '[data-testid="' + el.getAttribute('data-testid') + '"]';
    if (el.name && el.tagName === 'INPUT')
        return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
    const parent = el.parentElement;
    if (!parent) return el.tagName.toLowerCase();
    const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
    if (siblings.length === 1)
        return generateSelector(parent) + ' > ' + el.tagName.toLowerCase();
    const idx = siblings.indexOf(el) + 1;
    return generateSelector(parent) + ' > ' + el.tagName.toLowerCase() + ':nth-child(' + idx + ')';
}

const candidates = scope.querySelectorAll(query);
const seen = new Set();

candidates.forEach((el) => {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const tag = el.tagName.toLowerCase();
    if (['script','style','link','meta','head','html'].includes(tag)) return;

    if (checkCursor && !el.matches(arguments[3])) {
        const cs = window.getComputedStyle(el);
        if (cs.cursor !== 'pointer') return;
    }

    const sel = generateSelector(el);
    if (seen.has(sel)) return;
    seen.add(sel);

    const type = el.getAttribute('type') || '';
    const role = el.getAttribute('role') || '';
    const text = (el.textContent || '').trim().slice(0, 80);
    const placeholder = el.getAttribute('placeholder') || '';
    const name = el.getAttribute('name') || '';
    const ariaLabel = el.getAttribute('aria-label') || '';
    const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
    const value = el.value || '';
    const checked = !!el.checked;

    let desc = tag;
    if (type) desc += '[type=' + type + ']';
    if (role) desc += '[role=' + role + ']';

    elements.push({
        selector: sel,
        desc: desc,
        label: ariaLabel || text || placeholder || name || '',
        disabled: disabled,
        value: value,
        checked: checked,
        rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
    });
});
return elements;
"""

FIND_JS = """
const strategy = arguments[0];
const value = arguments[1];
const nameFilter = arguments[2];
let el = null;

if (strategy === 'text') {
    const all = document.querySelectorAll('*');
    for (const candidate of all) {
        if (candidate.children.length === 0 &&
            candidate.textContent.trim().includes(value)) {
            el = candidate;
            break;
        }
    }
    if (!el) {
        for (const candidate of all) {
            if (candidate.textContent.trim().includes(value)) {
                el = candidate;
                break;
            }
        }
    }
} else if (strategy === 'label') {
    el = document.querySelector('[aria-label="' + value.replace(/"/g, '\\\\"') + '"]');
} else if (strategy === 'role') {
    const implicitRoleTags = {
        button: 'button', link: 'a', textbox: 'input,textarea',
        heading: 'h1,h2,h3,h4,h5,h6', img: 'img', list: 'ul,ol',
        listitem: 'li', table: 'table', row: 'tr', cell: 'td,th',
        navigation: 'nav', main: 'main', form: 'form',
    };
    const explicit = Array.from(document.querySelectorAll('[role="' + value + '"]'));
    const implicitSel = implicitRoleTags[value] || '';
    const implicit = implicitSel
        ? Array.from(document.querySelectorAll(implicitSel)).filter(e => !e.getAttribute('role'))
        : [];
    const candidates = [...explicit, ...implicit];
    if (nameFilter) {
        for (const c of candidates) {
            const label = c.getAttribute('aria-label') || c.textContent.trim();
            if (label.includes(nameFilter)) { el = c; break; }
        }
    } else {
        el = candidates[0];
    }
} else if (strategy === 'testid') {
    el = document.querySelector('[data-testid="' + value + '"]');
} else if (strategy === 'placeholder') {
    el = document.querySelector('[placeholder="' + value.replace(/"/g, '\\\\"') + '"]');
}

if (!el) return null;

function generateSelector(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.getAttribute('data-testid'))
        return '[data-testid="' + el.getAttribute('data-testid') + '"]';
    if (el.name && el.tagName === 'INPUT')
        return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
    const parent = el.parentElement;
    if (!parent) return el.tagName.toLowerCase();
    const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
    if (siblings.length === 1)
        return generateSelector(parent) + ' > ' + el.tagName.toLowerCase();
    const idx = siblings.indexOf(el) + 1;
    return generateSelector(parent) + ' > ' + el.tagName.toLowerCase() + ':nth-child(' + idx + ')';
}

return generateSelector(el);
"""


# --- Configuration ---

def detect_xvfb_display():
    try:
        out = subprocess.check_output(
            ["pgrep", "-a", "Xvfb"], text=True, stderr=subprocess.DEVNULL)
        for line in out.strip().splitlines():
            for token in line.split():
                if token.startswith(":"):
                    return token
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


class Config:
    def __init__(self, session="default", driver=None, display=None):
        self.session = session
        self.driver = driver or os.environ.get(
            "TAURI_BROWSE_DRIVER", DEFAULT_DRIVER)
        self.display = (display
                        or os.environ.get("TAURI_BROWSE_DISPLAY")
                        or detect_xvfb_display()
                        or os.environ.get("DISPLAY"))
        if self.display:
            os.environ["DISPLAY"] = self.display


# --- HTTP / WebDriver ---

def request(driver, method, url, body=None, timeout=REQUEST_TIMEOUT):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_json = json.loads(error_body)
            msg = error_json.get("value", {}).get("message", error_body)
        except (json.JSONDecodeError, AttributeError):
            msg = error_body
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        print(f"Cannot connect to WebDriver at {driver}: {reason}",
              file=sys.stderr)
        print("Make sure tauri-driver is running.", file=sys.stderr)
        sys.exit(1)
    except TimeoutError:
        print(f"Request timed out after {timeout}s: {method} {url}",
              file=sys.stderr)
        sys.exit(1)


def request_quiet(method, url, body=None, timeout=REQUEST_TIMEOUT):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def surl(driver, sid):
    return f"{driver}/session/{sid}"


# --- Session Management ---

def ensure_dirs():
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    STATES_DIR.mkdir(parents=True, exist_ok=True)


def session_path(name):
    return SESSIONS_DIR / f"{name}.json"


def save_session(name, data):
    ensure_dirs()
    with open(session_path(name), "w") as f:
        json.dump(data, f)


def load_session(name):
    try:
        with open(session_path(name)) as f:
            return json.load(f)
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        print(f"No active session '{name}'. Run 'tauri-browse launch <binary>' first.",
              file=sys.stderr)
        sys.exit(1)


def delete_session(name):
    try:
        session_path(name).unlink()
    except FileNotFoundError:
        pass


def list_sessions():
    ensure_dirs()
    sessions = []
    for p in SESSIONS_DIR.glob("*.json"):
        try:
            with open(p) as f:
                data = json.load(f)
            sessions.append({
                "name": p.stem,
                "session_id": data.get("session_id", "unknown"),
            })
        except (json.JSONDecodeError, KeyError):
            pass
    return sessions


# --- Element Helpers ---

def resolve_target(state, target):
    if target.startswith("@e"):
        refs = state.get("refs", {})
        if target not in refs:
            print(f"Unknown ref: {target}. Run 'tauri-browse snapshot -i' to get refs.",
                  file=sys.stderr)
            sys.exit(1)
        return refs[target]
    return target


def find_element(config, sid, selector):
    resp = request(config.driver, "POST", f"{surl(config.driver, sid)}/element", {
        "using": "css selector",
        "value": selector,
    })
    return list(resp["value"].values())[0]


def try_find_element(config, sid, selector):
    result = request_quiet(
        "POST", f"{surl(config.driver, sid)}/element",
        {"using": "css selector", "value": selector})
    if result and "value" in result and isinstance(result["value"], dict):
        return list(result["value"].values())[0]
    return None


def find_by_strategy(config, sid, strategy, value, name_filter=None):
    resp = request(config.driver, "POST",
                   f"{surl(config.driver, sid)}/execute/sync", {
                       "script": FIND_JS,
                       "args": [strategy, value, name_filter],
                   })
    selector = resp["value"]
    if not selector:
        print(f"Element not found: {strategy}={value}", file=sys.stderr)
        sys.exit(1)
    return selector


# --- Snapshot ---

def collect_snapshot(config, sid, interactive, scope,
                     cursor_interactive=False):
    if cursor_interactive:
        query = CURSOR_INTERACTIVE_QUERY
    elif interactive:
        query = INTERACTIVE_QUERY
    else:
        query = '*'

    resp = request(config.driver, "POST",
                   f"{surl(config.driver, sid)}/execute/sync", {
                       "script": SNAPSHOT_JS,
                       "args": [scope, query, cursor_interactive,
                                INTERACTIVE_QUERY],
                   })
    elements = resp["value"]
    refs = {}
    lines = []
    for i, el in enumerate(elements):
        ref = f"@e{i + 1}"
        refs[ref] = el["selector"]
        desc = el["desc"]
        label = el["label"]
        parts = [ref, desc]
        if label:
            parts.append(f'"{label}"')
        if el["disabled"]:
            parts.append("[disabled]")
        if el["value"]:
            parts.append(f'value="{el["value"]}"')
        if el["checked"]:
            parts.append("[checked]")
        lines.append(" ".join(parts))
    return refs, lines, elements


# --- Screenshot ---

def webdriver_screenshot(config, sid):
    url = f"{surl(config.driver, sid)}/screenshot"
    result = request_quiet("GET", url, timeout=3)
    if result and "value" in result:
        return base64.b64decode(result["value"])
    return None


def x_display_screenshot(path):
    display = os.environ.get("DISPLAY")
    if not display:
        print("Screenshot failed: no DISPLAY set. Use --display or set DISPLAY.",
              file=sys.stderr)
        sys.exit(1)
    result = subprocess.run(
        ["import", "-window", "root", path],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"Screenshot failed: {result.stderr.decode().strip()}",
              file=sys.stderr)
        sys.exit(1)


def capture_screenshot(config, sid, path):
    display = os.environ.get("DISPLAY")
    if display:
        x_display_screenshot(path)
    else:
        png_data = webdriver_screenshot(config, sid)
        if png_data:
            with open(path, "wb") as f:
                f.write(png_data)
        else:
            print("Screenshot failed: WebDriver timed out and no DISPLAY set.",
                  file=sys.stderr)
            sys.exit(1)


def capture_full_screenshot(config, sid, path):
    scroll_h = request(config.driver, "POST",
                       f"{surl(config.driver, sid)}/execute/sync", {
                           "script": "return document.documentElement.scrollHeight",
                           "args": [],
                       })["value"]
    viewport_h = request(config.driver, "POST",
                         f"{surl(config.driver, sid)}/execute/sync", {
                             "script": "return window.innerHeight",
                             "args": [],
                         })["value"]

    if scroll_h <= viewport_h:
        capture_screenshot(config, sid, path)
        return

    segments = []
    offset = 0
    while offset < scroll_h:
        request(config.driver, "POST",
                f"{surl(config.driver, sid)}/execute/sync", {
                    "script": f"window.scrollTo(0, {offset})",
                    "args": [],
                })
        time.sleep(0.15)
        seg_path = os.path.join(tempfile.gettempdir(),
                                f"tb-seg-{len(segments)}.png")
        capture_screenshot(config, sid, seg_path)
        segments.append(seg_path)
        offset += viewport_h

    # Stitch segments vertically with ImageMagick
    result = subprocess.run(
        ["convert", "-append"] + segments + [path],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"Stitch failed: {result.stderr.decode().strip()}",
              file=sys.stderr)
        # Fall back to first segment
        import shutil
        shutil.copy2(segments[0], path)

    for seg in segments:
        os.unlink(seg)

    # Restore scroll position
    request(config.driver, "POST",
            f"{surl(config.driver, sid)}/execute/sync", {
                "script": "window.scrollTo(0, 0)",
                "args": [],
            })


def annotate_screenshot(path, elements):
    cmd = ["convert", path]
    for i, el in enumerate(elements):
        rect = el.get("rect")
        if not rect:
            continue
        x, y = int(rect["x"]), int(rect["y"])
        w, h = int(rect["w"]), int(rect["h"])
        num = str(i + 1)
        badge_w = 6 + len(num) * 8
        badge_h = 14
        bx, by = max(x - 1, 0), max(y - 1, 0)
        cmd.extend([
            "-stroke", "rgba(59,130,246,0.5)", "-strokewidth", "1",
            "-fill", "none",
            "-draw", f"rectangle {x},{y} {x + w},{y + h}",
        ])
        cmd.extend([
            "-stroke", "none", "-fill", "rgba(220,38,38,0.9)",
            "-draw", f"roundrectangle {bx},{by} {bx + badge_w},{by + badge_h} 2,2",
        ])
        cmd.extend([
            "-fill", "white", "-pointsize", "11",
            "-draw", f"text {bx + 2},{by + 11} '{num}'",
        ])
    cmd.append(path)
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"Annotation failed: {result.stderr.decode().strip()}",
              file=sys.stderr)


def diff_screenshots(baseline, current, output):
    result = subprocess.run(
        ["compare", "-metric", "AE", "-fuzz", "5%",
         baseline, current, output],
        capture_output=True,
    )
    # compare returns exit code 1 if images differ, 0 if identical
    stderr = result.stderr.decode().strip()
    try:
        diff_pixels = int(stderr)
    except ValueError:
        diff_pixels = -1

    # Get image dimensions for percentage calculation
    identify = subprocess.run(
        ["identify", "-format", "%w %h", baseline],
        capture_output=True, text=True,
    )
    if identify.returncode == 0:
        parts = identify.stdout.strip().split()
        total = int(parts[0]) * int(parts[1])
        if total > 0 and diff_pixels >= 0:
            pct = (diff_pixels / total) * 100
            print(f"Diff pixels: {diff_pixels} ({pct:.2f}%)")
            print(f"Diff image: {output}")
            return
    print(f"Diff pixels: {stderr}")
    print(f"Diff image: {output}")


# --- Commands ---

def cmd_launch(config, args):
    if not args:
        print("Usage: tauri-browse launch <path-to-binary>", file=sys.stderr)
        sys.exit(1)

    binary = os.path.abspath(args[0])
    if not os.path.isfile(binary):
        print(f"Binary not found: {binary}", file=sys.stderr)
        sys.exit(1)

    resp = request(config.driver, "POST", f"{config.driver}/session", {
        "capabilities": {
            "alwaysMatch": {
                "browserName": "wry",
                "tauri:options": {
                    "application": binary,
                },
            }
        }
    }, timeout=30)
    sid = resp["value"]["sessionId"]
    save_session(config.session, {
        "session_id": sid, "refs": {}, "last_snapshot": "",
        "last_screenshot": "",
    })
    print(f"Session started: {sid}")

    time.sleep(2)
    url = request(config.driver, "GET", f"{surl(config.driver, sid)}/url")
    print(f"URL: {url['value']}")


def cmd_open(config, args):
    if not args:
        print("Usage: tauri-browse open <url>", file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    request(config.driver, "POST", f"{surl(config.driver, sid)}/url",
            {"url": args[0]})
    print(f"Navigated to {args[0]}")


def cmd_close(config, _args):
    state = load_session(config.session)
    request_quiet("DELETE",
                  surl(config.driver, state["session_id"]))
    delete_session(config.session)
    print("Session closed.")


def cmd_snapshot(config, args):
    state = load_session(config.session)
    sid = state["session_id"]
    interactive = "-i" in args
    cursor_interactive = "-C" in args
    as_json = "--json" in args
    scope = None
    if "-s" in args:
        idx = args.index("-s")
        if idx + 1 < len(args):
            scope = args[idx + 1]

    refs, lines, elements = collect_snapshot(
        config, sid, interactive or cursor_interactive, scope,
        cursor_interactive)

    if as_json:
        output = []
        for i, el in enumerate(elements):
            output.append({
                "ref": f"@e{i + 1}",
                "selector": el["selector"],
                "desc": el["desc"],
                "label": el["label"],
                "disabled": el["disabled"],
                "value": el["value"],
                "checked": el["checked"],
                "rect": el["rect"],
            })
        print(json.dumps(output, indent=2))
    else:
        for line in lines:
            print(line)

    state["refs"] = refs
    state["last_snapshot"] = "\n".join(lines)
    save_session(config.session, state)


def cmd_screenshot(config, args):
    state = load_session(config.session)
    sid = state["session_id"]
    do_annotate = "--annotate" in args
    do_full = "--full" in args

    path = None
    for a in args:
        if not a.startswith("-"):
            path = a
            break
    if not path:
        path = os.path.join(tempfile.gettempdir(),
                            f"tauri-browse-{int(time.time())}.png")

    if do_full:
        capture_full_screenshot(config, sid, path)
    else:
        capture_screenshot(config, sid, path)

    state["last_screenshot"] = path
    save_session(config.session, state)

    if do_annotate:
        refs, lines, elements = collect_snapshot(config, sid, True, None)
        annotate_screenshot(path, elements)
        state["refs"] = refs
        state["last_snapshot"] = "\n".join(lines)
        save_session(config.session, state)
        print(path)
        for i, el in enumerate(elements):
            ref = f"@e{i + 1}"
            desc = el["desc"]
            label = el["label"]
            label_str = f' "{label}"' if label else ""
            print(f"  [{i + 1}] {ref} {desc}{label_str}")
    else:
        print(path)


def cmd_click(config, args):
    if not args:
        print("Usage: tauri-browse click <@ref|selector>", file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    selector = resolve_target(state, args[0])
    element_id = find_element(config, sid, selector)
    request(config.driver, "POST",
            f"{surl(config.driver, sid)}/element/{element_id}/click", {})
    print("Clicked.")


def cmd_fill(config, args):
    if len(args) < 2:
        print("Usage: tauri-browse fill <@ref|selector> <text>",
              file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    selector = resolve_target(state, args[0])
    element_id = find_element(config, sid, selector)
    request(config.driver, "POST",
            f"{surl(config.driver, sid)}/element/{element_id}/clear", {})
    request(config.driver, "POST",
            f"{surl(config.driver, sid)}/element/{element_id}/value",
            {"text": args[1]})
    print("Filled.")


def cmd_type(config, args):
    if len(args) < 2:
        print("Usage: tauri-browse type <@ref|selector> <text>",
              file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    selector = resolve_target(state, args[0])
    element_id = find_element(config, sid, selector)
    request(config.driver, "POST",
            f"{surl(config.driver, sid)}/element/{element_id}/value",
            {"text": args[1]})
    print("Typed.")


def cmd_select(config, args):
    if len(args) < 2:
        print("Usage: tauri-browse select <@ref|selector> <option-text>",
              file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    selector = resolve_target(state, args[0])
    script = """
    const sel = document.querySelector(arguments[0]);
    if (!sel) throw new Error('Element not found: ' + arguments[0]);
    const opt = Array.from(sel.options).find(
        o => o.text === arguments[1] || o.value === arguments[1]
    );
    if (!opt) throw new Error('Option not found: ' + arguments[1]);
    sel.value = opt.value;
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    return opt.text;
    """
    resp = request(config.driver, "POST",
                   f"{surl(config.driver, sid)}/execute/sync",
                   {"script": script, "args": [selector, args[1]]})
    print(f"Selected: {resp['value']}")


def cmd_check(config, args):
    if not args:
        print("Usage: tauri-browse check <@ref|selector>", file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    selector = resolve_target(state, args[0])
    element_id = find_element(config, sid, selector)
    request(config.driver, "POST",
            f"{surl(config.driver, sid)}/element/{element_id}/click", {})
    print("Toggled.")


def cmd_press(config, args):
    if not args:
        print("Usage: tauri-browse press <key>", file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    key_name = args[0]
    value = SPECIAL_KEYS.get(key_name.lower(), key_name)
    request(config.driver, "POST", f"{surl(config.driver, sid)}/actions", {
        "actions": [{
            "type": "key",
            "id": "keyboard",
            "actions": [
                {"type": "keyDown", "value": value},
                {"type": "keyUp", "value": value},
            ]
        }]
    })
    print(f"Pressed: {key_name}")


def cmd_scroll(config, args):
    if len(args) < 2:
        print("Usage: tauri-browse scroll <up|down|left|right> <amount>",
              file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    direction = args[0].lower()
    amount = int(args[1])
    scroll_map = {
        "up": (0, -amount), "down": (0, amount),
        "left": (-amount, 0), "right": (amount, 0),
    }
    if direction not in scroll_map:
        print(f"Unknown direction: {direction}. Use up/down/left/right.",
              file=sys.stderr)
        sys.exit(1)

    x, y = scroll_map[direction]
    request(config.driver, "POST",
            f"{surl(config.driver, sid)}/execute/sync",
            {"script": f"window.scrollBy({x}, {y})", "args": []})
    print(f"Scrolled {direction} {amount}px.")


def cmd_highlight(config, args):
    if not args:
        print("Usage: tauri-browse highlight <@ref|selector>",
              file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    selector = resolve_target(state, args[0])
    script = """
    const el = document.querySelector(arguments[0]);
    if (!el) throw new Error('Element not found: ' + arguments[0]);
    const orig = el.style.outline;
    el.style.outline = '3px solid red';
    el.style.outlineOffset = '2px';
    setTimeout(() => {
        el.style.outline = orig;
        el.style.outlineOffset = '';
    }, 3000);
    return true;
    """
    request(config.driver, "POST",
            f"{surl(config.driver, sid)}/execute/sync",
            {"script": script, "args": [selector]})
    print(f"Highlighted for 3s.")


def cmd_find(config, args):
    if len(args) < 3:
        print("Usage: tauri-browse find <text|label|role|testid|placeholder>"
              " <value> <action> [action-args]", file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]

    strategy = args[0]
    value = args[1]
    action = args[2]
    action_args = args[3:]

    name_filter = None
    if "--name" in action_args:
        idx = action_args.index("--name")
        if idx + 1 < len(action_args):
            name_filter = action_args[idx + 1]
            action_args = action_args[:idx] + action_args[idx + 2:]

    selector = find_by_strategy(config, sid, strategy, value, name_filter)
    element_id = find_element(config, sid, selector)

    if action == "click":
        request(config.driver, "POST",
                f"{surl(config.driver, sid)}/element/{element_id}/click", {})
        print("Clicked.")
    elif action == "fill":
        if not action_args:
            print("Usage: find ... fill <text>", file=sys.stderr)
            sys.exit(1)
        request(config.driver, "POST",
                f"{surl(config.driver, sid)}/element/{element_id}/clear", {})
        request(config.driver, "POST",
                f"{surl(config.driver, sid)}/element/{element_id}/value",
                {"text": action_args[0]})
        print("Filled.")
    elif action == "type":
        if not action_args:
            print("Usage: find ... type <text>", file=sys.stderr)
            sys.exit(1)
        request(config.driver, "POST",
                f"{surl(config.driver, sid)}/element/{element_id}/value",
                {"text": action_args[0]})
        print("Typed.")
    elif action == "check":
        request(config.driver, "POST",
                f"{surl(config.driver, sid)}/element/{element_id}/click", {})
        print("Toggled.")
    elif action == "highlight":
        cmd_highlight(config, [selector])
    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        sys.exit(1)


def cmd_eval(config, args):
    read_stdin = "--stdin" in args
    clean_args = [a for a in args if a != "--stdin"]

    if read_stdin:
        script = sys.stdin.read()
    elif clean_args:
        script = clean_args[0]
    else:
        print("Usage: tauri-browse eval <js> [--stdin]", file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    resp = request(config.driver, "POST",
                   f"{surl(config.driver, sid)}/execute/sync",
                   {"script": script, "args": []})
    result = resp["value"]
    if result is not None:
        if isinstance(result, (dict, list)):
            print(json.dumps(result, indent=2))
        else:
            print(result)


def cmd_get(config, args):
    if not args:
        print("Usage: tauri-browse get <text|url|title> [@ref|selector]",
              file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    subcmd = args[0]

    if subcmd == "url":
        resp = request(config.driver, "GET",
                       f"{surl(config.driver, sid)}/url")
        print(resp["value"])
    elif subcmd == "title":
        resp = request(config.driver, "GET",
                       f"{surl(config.driver, sid)}/title")
        print(resp["value"])
    elif subcmd == "text":
        if len(args) < 2:
            print("Usage: tauri-browse get text <@ref|selector>",
                  file=sys.stderr)
            sys.exit(1)
        selector = resolve_target(state, args[1])
        element_id = find_element(config, sid, selector)
        resp = request(config.driver, "GET",
                       f"{surl(config.driver, sid)}/element/{element_id}/text")
        print(resp["value"])
    else:
        print(f"Unknown get subcommand: {subcmd}", file=sys.stderr)
        sys.exit(1)


def cmd_wait(config, args):
    if not args:
        print("Usage: tauri-browse wait <@ref|selector|ms> "
              "[--url|--load|--fn]", file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]

    if args[0] == "--url":
        if len(args) < 2:
            print("Usage: tauri-browse wait --url <pattern>",
                  file=sys.stderr)
            sys.exit(1)
        pattern = args[1]
        timeout_ms = int(args[2]) if len(args) > 2 else 10000
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            resp = request(config.driver, "GET",
                           f"{surl(config.driver, sid)}/url")
            if pattern in resp["value"]:
                print(f"URL matched: {resp['value']}")
                return
            time.sleep(0.25)
        print(f"Timeout waiting for URL containing: {pattern}",
              file=sys.stderr)
        sys.exit(1)

    if args[0] == "--load":
        strategy = args[1] if len(args) > 1 else "networkidle"
        timeout_ms = int(args[2]) if len(args) > 2 else 10000
        deadline = time.time() + timeout_ms / 1000
        if strategy == "networkidle":
            # Wait for document.readyState complete + 500ms stability
            settled_at = None
            while time.time() < deadline:
                resp = request(config.driver, "POST",
                               f"{surl(config.driver, sid)}/execute/sync", {
                                   "script": "return document.readyState",
                                   "args": [],
                               })
                if resp["value"] == "complete":
                    if settled_at is None:
                        settled_at = time.time()
                    elif time.time() - settled_at >= 0.5:
                        print("Network idle.")
                        return
                else:
                    settled_at = None
                time.sleep(0.1)
            print("Timeout waiting for network idle.", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Unknown load strategy: {strategy}", file=sys.stderr)
            sys.exit(1)

    if args[0] == "--fn":
        if len(args) < 2:
            print("Usage: tauri-browse wait --fn <js-expression>",
                  file=sys.stderr)
            sys.exit(1)
        expr = args[1]
        timeout_ms = int(args[2]) if len(args) > 2 else 10000
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            resp = request(config.driver, "POST",
                           f"{surl(config.driver, sid)}/execute/sync", {
                               "script": f"return !!({expr})",
                               "args": [],
                           })
            if resp["value"]:
                print("Condition met.")
                return
            time.sleep(0.25)
        print(f"Timeout waiting for: {expr}", file=sys.stderr)
        sys.exit(1)

    target = args[0]

    if target.isdigit():
        ms = int(target)
        time.sleep(ms / 1000)
        print(f"Waited {ms}ms.")
        return

    selector = resolve_target(state, target)
    timeout_ms = int(args[1]) if len(args) > 1 else 10000
    deadline = time.time() + timeout_ms / 1000

    while time.time() < deadline:
        if try_find_element(config, sid, selector) is not None:
            print(f"Found: {selector}")
            return
        time.sleep(0.25)

    print(f"Timeout waiting for: {selector}", file=sys.stderr)
    sys.exit(1)


def cmd_diff(config, args):
    if not args:
        print("Usage: tauri-browse diff <snapshot|screenshot|url> [options]",
              file=sys.stderr)
        sys.exit(1)

    state = load_session(config.session)
    sid = state["session_id"]
    subcmd = args[0]

    if subcmd == "snapshot":
        if "--baseline" in args:
            idx = args.index("--baseline")
            if idx + 1 >= len(args):
                print("Usage: tauri-browse diff snapshot --baseline <file>",
                      file=sys.stderr)
                sys.exit(1)
            with open(args[idx + 1]) as f:
                old_lines = f.read().strip().splitlines()
        else:
            old_text = state.get("last_snapshot", "")
            if not old_text:
                print("No previous snapshot. Run 'snapshot -i' first.",
                      file=sys.stderr)
                sys.exit(1)
            old_lines = old_text.strip().splitlines()

        refs, new_lines, _ = collect_snapshot(config, sid, True, None)
        state["refs"] = refs
        state["last_snapshot"] = "\n".join(new_lines)
        save_session(config.session, state)

        old_set = set(old_lines)
        new_set = set(new_lines)
        removed = [l for l in old_lines if l not in new_set]
        added = [l for l in new_lines if l not in old_set]

        if not removed and not added:
            print("No changes.")
            return
        for line in removed:
            print(f"- {line}")
        for line in added:
            print(f"+ {line}")

    elif subcmd == "screenshot":
        if "--baseline" not in args:
            print("Usage: tauri-browse diff screenshot --baseline <file>",
                  file=sys.stderr)
            sys.exit(1)
        idx = args.index("--baseline")
        if idx + 1 >= len(args):
            print("Usage: tauri-browse diff screenshot --baseline <file>",
                  file=sys.stderr)
            sys.exit(1)
        baseline = args[idx + 1]
        current = os.path.join(tempfile.gettempdir(),
                               f"tb-diff-current-{int(time.time())}.png")
        capture_screenshot(config, sid, current)
        output = os.path.join(tempfile.gettempdir(),
                              f"tb-diff-{int(time.time())}.png")
        diff_screenshots(baseline, current, output)
        os.unlink(current)

    elif subcmd == "url":
        if len(args) < 3:
            print("Usage: tauri-browse diff url <url1> <url2> "
                  "[--screenshot] [--selector SEL]", file=sys.stderr)
            sys.exit(1)
        url1, url2 = args[1], args[2]
        do_screenshot = "--screenshot" in args
        sel = None
        if "--selector" in args:
            si = args.index("--selector")
            if si + 1 < len(args):
                sel = args[si + 1]

        scope = sel if sel else None

        if do_screenshot:
            img1 = os.path.join(tempfile.gettempdir(), "tb-diff-url1.png")
            img2 = os.path.join(tempfile.gettempdir(), "tb-diff-url2.png")

            request(config.driver, "POST",
                    f"{surl(config.driver, sid)}/url", {"url": url1})
            time.sleep(1)
            capture_screenshot(config, sid, img1)

            request(config.driver, "POST",
                    f"{surl(config.driver, sid)}/url", {"url": url2})
            time.sleep(1)
            capture_screenshot(config, sid, img2)

            output = os.path.join(tempfile.gettempdir(),
                                  f"tb-diff-url-{int(time.time())}.png")
            diff_screenshots(img1, img2, output)
            os.unlink(img1)
            os.unlink(img2)
        else:
            request(config.driver, "POST",
                    f"{surl(config.driver, sid)}/url", {"url": url1})
            time.sleep(1)
            _, lines1, _ = collect_snapshot(config, sid, True, scope)

            request(config.driver, "POST",
                    f"{surl(config.driver, sid)}/url", {"url": url2})
            time.sleep(1)
            _, lines2, _ = collect_snapshot(config, sid, True, scope)

            set1 = set(lines1)
            set2 = set(lines2)
            removed = [l for l in lines1 if l not in set2]
            added = [l for l in lines2 if l not in set1]
            if not removed and not added:
                print("No changes.")
            else:
                for line in removed:
                    print(f"- {line}")
                for line in added:
                    print(f"+ {line}")
    else:
        print(f"Unknown diff subcommand: {subcmd}", file=sys.stderr)
        sys.exit(1)


def cmd_session(config, args):
    if not args:
        print("Usage: tauri-browse session list", file=sys.stderr)
        sys.exit(1)

    if args[0] == "list":
        sessions = list_sessions()
        if not sessions:
            print("No active sessions.")
        else:
            for s in sessions:
                marker = " *" if s["name"] == config.session else ""
                print(f"  {s['name']}{marker} ({s['session_id'][:12]}...)")
    else:
        print(f"Unknown session subcommand: {args[0]}", file=sys.stderr)
        sys.exit(1)


def cmd_state(config, args):
    if not args:
        print("Usage: tauri-browse state <save|load|list|clear> [args]",
              file=sys.stderr)
        sys.exit(1)

    subcmd = args[0]

    if subcmd == "save":
        if len(args) < 2:
            print("Usage: tauri-browse state save <file>", file=sys.stderr)
            sys.exit(1)
        state = load_session(config.session)
        sid = state["session_id"]

        cookies = request(config.driver, "GET",
                          f"{surl(config.driver, sid)}/cookie")["value"]
        ls_resp = request(config.driver, "POST",
                          f"{surl(config.driver, sid)}/execute/sync", {
                              "script": "return JSON.stringify(localStorage)",
                              "args": [],
                          })
        local_storage = json.loads(ls_resp["value"]) if ls_resp["value"] else {}
        url = request(config.driver, "GET",
                      f"{surl(config.driver, sid)}/url")["value"]

        save_path = args[1]
        if not os.path.isabs(save_path):
            ensure_dirs()
            save_path = str(STATES_DIR / save_path)

        with open(save_path, "w") as f:
            json.dump({
                "cookies": cookies,
                "localStorage": local_storage,
                "url": url,
            }, f, indent=2)
        print(f"State saved: {save_path}")

    elif subcmd == "load":
        if len(args) < 2:
            print("Usage: tauri-browse state load <file>", file=sys.stderr)
            sys.exit(1)
        state = load_session(config.session)
        sid = state["session_id"]

        load_path = args[1]
        if not os.path.isabs(load_path) and not os.path.exists(load_path):
            load_path = str(STATES_DIR / load_path)

        with open(load_path) as f:
            data = json.load(f)

        if data.get("url"):
            request(config.driver, "POST", f"{surl(config.driver, sid)}/url",
                    {"url": data["url"]})
            time.sleep(1)

        for cookie in data.get("cookies", []):
            request_quiet("POST",
                          f"{surl(config.driver, sid)}/cookie",
                          {"cookie": cookie})

        ls = data.get("localStorage", {})
        if ls:
            for key, value in ls.items():
                request(config.driver, "POST",
                        f"{surl(config.driver, sid)}/execute/sync", {
                            "script": "localStorage.setItem(arguments[0], arguments[1])",
                            "args": [key, value],
                        })
        print(f"State loaded: {load_path}")

    elif subcmd == "list":
        ensure_dirs()
        files = sorted(STATES_DIR.glob("*.json"))
        if not files:
            print("No saved states.")
        else:
            for f in files:
                size = f.stat().st_size
                print(f"  {f.name} ({size} bytes)")

    elif subcmd == "clear":
        ensure_dirs()
        if len(args) > 1:
            target = STATES_DIR / args[1]
            if not target.suffix:
                target = target.with_suffix(".json")
            try:
                target.unlink()
                print(f"Cleared: {target.name}")
            except FileNotFoundError:
                print(f"Not found: {target.name}", file=sys.stderr)
        else:
            count = 0
            for f in STATES_DIR.glob("*.json"):
                f.unlink()
                count += 1
            print(f"Cleared {count} state files.")
    else:
        print(f"Unknown state subcommand: {subcmd}", file=sys.stderr)
        sys.exit(1)


# --- Dispatch ---

COMMANDS = {
    "launch": cmd_launch,
    "open": cmd_open,
    "goto": cmd_open,
    "navigate": cmd_open,
    "close": cmd_close,
    "snapshot": cmd_snapshot,
    "screenshot": cmd_screenshot,
    "click": cmd_click,
    "fill": cmd_fill,
    "type": cmd_type,
    "select": cmd_select,
    "check": cmd_check,
    "press": cmd_press,
    "scroll": cmd_scroll,
    "highlight": cmd_highlight,
    "find": cmd_find,
    "eval": cmd_eval,
    "get": cmd_get,
    "wait": cmd_wait,
    "diff": cmd_diff,
    "session": cmd_session,
    "state": cmd_state,
}


def main():
    argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help", "help"):
        print((__doc__ or "").strip())
        sys.exit(0)

    if argv[0] in ("-v", "--version"):
        print(f"tauri-browse {VERSION}")
        sys.exit(0)

    # Parse global options
    session = "default"
    driver = None
    display = None

    i = 0
    while i < len(argv):
        if argv[i] == "--session" and i + 1 < len(argv):
            session = argv[i + 1]
            i += 2
        elif argv[i] == "--driver" and i + 1 < len(argv):
            driver = argv[i + 1]
            i += 2
        elif argv[i] == "--display" and i + 1 < len(argv):
            display = argv[i + 1]
            i += 2
        else:
            break

    remaining = argv[i:]
    if not remaining:
        print((__doc__ or "").strip())
        sys.exit(0)

    cmd_name = remaining[0]
    cmd_args = remaining[1:]

    if cmd_name not in COMMANDS:
        print(f"Unknown command: {cmd_name}", file=sys.stderr)
        print(f"Available: {', '.join(sorted(COMMANDS.keys()))}",
              file=sys.stderr)
        sys.exit(1)

    config = Config(session=session, driver=driver, display=display)
    COMMANDS[cmd_name](config, cmd_args)


if __name__ == "__main__":
    main()
