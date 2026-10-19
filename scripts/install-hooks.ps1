# Use the repository's hooks in .githooks/ (commit message hygiene). Run once per clone.
Set-Location (git rev-parse --show-toplevel)
git config core.hooksPath .githooks
Write-Output "Git hooks installed: core.hooksPath = .githooks"
