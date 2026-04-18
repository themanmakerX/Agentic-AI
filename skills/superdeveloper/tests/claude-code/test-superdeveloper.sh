#!/usr/bin/env bash
# Test: superdeveloper skill
# Verifies that the skill is loaded and describes the orchestration contract
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/test-helpers.sh"

echo "=== Test: superdeveloper skill ==="
echo ""

# Test 1: Verify skill can be loaded
echo "Test 1: Skill loading..."

output=$(run_claude "What is the superdeveloper skill? Summarize its core workflow in a few bullets." 30)

if assert_contains "$output" "superdeveloper\|Superdeveloper" "Skill is recognized"; then
    : # pass
else
    exit 1
fi

if assert_contains "$output" "platform.*detect\|detect.*platform\|Codex\|Claude Code\|OpenCode\|Cursor\|Gemini" "Mentions platform detection"; then
    : # pass
else
    exit 1
fi

if assert_contains "$output" "documentation\|README\|usage manual\|developer manual" "Mentions documentation outputs"; then
    : # pass
else
    exit 1
fi

echo ""

# Test 2: Verify platform detection comes before implementation
echo "Test 2: Platform detection order..."

output=$(run_claude "In superdeveloper, what should happen first: platform detection or implementation? Be specific." 30)

if assert_order "$output" "platform.*detect\|detect.*platform" "implement\|implementation" "Platform detection before implementation"; then
    : # pass
else
    exit 1
fi

echo ""

# Test 3: Verify the multi-agent team includes the required roles
echo "Test 3: Team composition..."

output=$(run_claude "What agents make up a superdeveloper phase team? Include the special reviewer role." 30)

if assert_contains "$output" "lead\|builder\|reviewer\|devil" "Lists team roles"; then
    : # pass
else
    exit 1
fi

if assert_contains "$output" "devil.*advocate" "Devil's advocate included"; then
    : # pass
else
    exit 1
fi

if assert_contains "$output" "documentation agent\|documentation" "Documentation agent included"; then
    : # pass
else
    exit 1
fi

echo ""

# Test 4: Verify final docs are required
echo "Test 4: Final documentation outputs..."

output=$(run_claude "At the end of superdeveloper, what documentation files must be produced?" 30)

if assert_contains "$output" "README\.md" "README required"; then
    : # pass
else
    exit 1
fi

if assert_contains "$output" "usage manual\|USAGE\.md" "Usage manual required"; then
    : # pass
else
    exit 1
fi

if assert_contains "$output" "developer manual\|DEVELOPER\.md" "Developer manual required"; then
    : # pass
else
    exit 1
fi

echo ""

echo "=== All superdeveloper skill tests passed ==="
