#!/bin/bash
set -e
HOOK=".git/hooks/pre-push"
SRC="cv-pilot-agent/scripts/hooks/pre-push"

if [ ! -f "$SRC" ]; then
    echo "Error: $SRC not found. Is the working directory correct?" >&2
    exit 1
fi

if [ -f "$HOOK" ]; then
    cp "$HOOK" "${HOOK}.bak"
    echo "Backed up existing hook to ${HOOK}.bak"
fi
cp "$SRC" "$HOOK"
chmod +x "$HOOK"
echo "Pre-push hook installed."
