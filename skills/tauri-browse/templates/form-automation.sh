#!/bin/bash
# Template: Form Automation Workflow
# Purpose: Fill and submit web forms in a Tauri app
# Usage: ./form-automation.sh <tauri-binary>
#
# This template demonstrates the snapshot-interact-verify pattern:
# 1. Launch Tauri app
# 2. Snapshot to get element refs
# 3. Fill fields using refs
# 4. Submit and verify result
#
# Customize: Update the refs (@e1, @e2, etc.) based on your app's snapshot output

set -euo pipefail

APP_BINARY="${1:?Usage: $0 <tauri-binary>}"

echo "Form automation: $APP_BINARY"

# Step 1: Launch the Tauri app
tauri-browse launch "$APP_BINARY"
tauri-browse wait --load networkidle

# Step 2: Snapshot to discover form elements
echo ""
echo "Form structure:"
tauri-browse snapshot -i

# Step 3: Fill form fields (customize these refs based on snapshot output)
#
# Common field types:
#   tauri-browse fill @e1 "John Doe"           # Text input
#   tauri-browse fill @e2 "user@example.com"   # Email input
#   tauri-browse fill @e3 "SecureP@ss123"      # Password input
#   tauri-browse select @e4 "Option Value"     # Dropdown
#   tauri-browse check @e5                     # Checkbox
#   tauri-browse click @e6                     # Radio button
#   tauri-browse fill @e7 "Multi-line text"    # Textarea
#
# Uncomment and modify:
# tauri-browse fill @e1 "Test User"
# tauri-browse fill @e2 "test@example.com"
# tauri-browse click @e3  # Submit button

# Step 4: Wait for submission
# tauri-browse wait --load networkidle
# tauri-browse wait --url "/success"  # Or wait for redirect

# Step 5: Verify result
echo ""
echo "Result:"
tauri-browse get url
tauri-browse snapshot -i

# Optional: Capture evidence
tauri-browse screenshot /tmp/form-result.png
echo "Screenshot saved: /tmp/form-result.png"

# Cleanup
tauri-browse close
echo "Done"
