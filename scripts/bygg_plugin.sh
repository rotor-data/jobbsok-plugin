#!/bin/sh
# Bygger dist/jobbsok-<version>.plugin: en zip med plugin-roten (enligt create-cowork-plugin),
# utan tester, fixturer och cachefiler.
set -eu
ROT=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$ROT/plugin/.claude-plugin/plugin.json")
UT="$ROT/dist/jobbsok-$VERSION.plugin"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$ROT/dist"
rm -f "$UT"
cd "$ROT/plugin"
zip -rq "$TMP/jobbsok.plugin" . -x "tests/*" "*/__pycache__/*" "__pycache__/*" "*.pyc" "*.DS_Store"
cp "$TMP/jobbsok.plugin" "$UT"
echo "$UT"
