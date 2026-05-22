#!/usr/bin/env bash
# Test script for stepfun-asr skill
# Runs unit tests only (no API key required)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  Testing stepfun-asr"
echo "=========================================="
echo ""

PYTHONPATH="$SCRIPT_DIR:../stepfun-image:../stepfun-tts" python3 -m pytest \
  "$SCRIPT_DIR/../tests/test_stepfun_asr.py" \
  -v -k "not Integration"

echo ""
echo "=========================================="
echo "  All stepfun-asr tests passed!"
echo "=========================================="
