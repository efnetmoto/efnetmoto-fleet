#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

[[ "$FILE" == *.tcl ]] || exit 0

if ! command -v tclfmt &>/dev/null || ! command -v tclint &>/dev/null; then
    echo "Note: tclfmt/tclint not found. See Dev Prerequisites in CONTRIBUTING.md."
    exit 0
fi

tclfmt "$FILE" 2>/dev/null || true

RESULT=$(tclint "$FILE" 2>&1)
if [ -n "$RESULT" ]; then
    echo "tclint: $FILE"
    echo "$RESULT"
fi
