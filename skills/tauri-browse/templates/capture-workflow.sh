#!/bin/bash
# Template: Content Capture Workflow
# Purpose: Extract content from a Tauri app (text, screenshots)
# Usage: ./capture-workflow.sh <tauri-binary> [output-dir]
#
# Outputs:
#   - page-full.png: Full page screenshot
#   - page-structure.txt: Page element structure with refs
#   - page-text.txt: All text content
#
# Optional: Load auth state for protected pages

set -euo pipefail

APP_BINARY="${1:?Usage: $0 <tauri-binary> [output-dir]}"
OUTPUT_DIR="${2:-.}"

echo "Capturing: $APP_BINARY"
mkdir -p "$OUTPUT_DIR"

# Optional: Load authentication state
# if [[ -f "./auth-state.json" ]]; then
#     echo "Loading authentication state..."
#     tauri-browse state load "./auth-state.json"
# fi

# Launch the Tauri app
tauri-browse launch "$APP_BINARY"
tauri-browse wait --load networkidle

# Get metadata
TITLE=$(tauri-browse get title)
URL=$(tauri-browse get url)
echo "Title: $TITLE"
echo "URL: $URL"

# Capture full page screenshot
tauri-browse screenshot --full "$OUTPUT_DIR/page-full.png"
echo "Saved: $OUTPUT_DIR/page-full.png"

# Get page structure with refs
tauri-browse snapshot -i > "$OUTPUT_DIR/page-structure.txt"
echo "Saved: $OUTPUT_DIR/page-structure.txt"

# Extract all text content
tauri-browse get text body > "$OUTPUT_DIR/page-text.txt"
echo "Saved: $OUTPUT_DIR/page-text.txt"

# Optional: Extract specific elements using refs from structure
# tauri-browse get text @e5 > "$OUTPUT_DIR/main-content.txt"

# Optional: Handle scrollable content
# for i in {1..5}; do
#     tauri-browse scroll down 1000
#     tauri-browse wait 1000
# done
# tauri-browse screenshot --full "$OUTPUT_DIR/page-scrolled.png"

# Cleanup
tauri-browse close

echo ""
echo "Capture complete:"
ls -la "$OUTPUT_DIR"
