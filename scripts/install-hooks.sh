#!/bin/sh
# Use the repository's hooks in .githooks/ (commit message hygiene). Run once per clone.
set -e
cd "$(git rev-parse --show-toplevel)"
chmod +x .githooks/*
git config core.hooksPath .githooks
echo "Git hooks installed: core.hooksPath = .githooks"
