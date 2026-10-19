<#
.SYNOPSIS
  Publish the deployed site's URL: the README "Live demo" line and the repository's homepage (About section),
  then commit and push.

.EXAMPLE
  .\scripts\set-live-url.ps1 -Url https://vetagent.vercel.app

.EXAMPLE
  .\scripts\set-live-url.ps1 -Url https://vetagent.vercel.app -DryRun   # show the new README line, change nothing

.NOTES
  Needs git and the GitHub CLI (gh), signed in to the repository owner's account (gh auth login).
  Safe to run again with a new URL: it replaces the block between the LIVE_DEMO_URL markers.
#>
param(
  [Parameter(Mandatory = $true)][string]$Url,
  [string]$Repo = "Shubhomoy919/VetAgent",
  [switch]$NoPush,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Url = $Url.Trim().TrimEnd("/")
if ($Url -notmatch '^https://[A-Za-z0-9.-]+(:\d+)?(/\S*)?$') {
  throw "Give the full https:// address of the deployment, for example https://vetagent.vercel.app"
}

Set-Location (git rev-parse --show-toplevel)
$path = Join-Path (Get-Location) "README.md"
$readme = [System.IO.File]::ReadAllText($path)
$pattern = '(?s)<!-- LIVE_DEMO_URL.*?-->.*?<!-- /LIVE_DEMO_URL -->'
if ($readme -notmatch $pattern) { throw "README.md has no LIVE_DEMO_URL block to replace" }

$block = "<!-- LIVE_DEMO_URL: set by scripts/set-live-url.ps1 -->`n" +
         "**Live demo:** [$Url]($Url) (read-only for visitors; live runs need the access code)`n" +
         "<!-- /LIVE_DEMO_URL -->"
$updated = [regex]::Replace($readme, $pattern, [System.Text.RegularExpressions.MatchEvaluator] { param($m) $block })

if ($DryRun) {
  Write-Output "README.md would get:"
  Write-Output $block
  Write-Output "and the repository homepage would be set with: gh repo edit $Repo --homepage $Url"
  exit 0
}

[System.IO.File]::WriteAllText($path, $updated, (New-Object System.Text.UTF8Encoding $false))
Write-Output "README.md: Live demo line set to $Url"

gh repo edit $Repo --homepage $Url
if ($LASTEXITCODE -ne 0) { throw "gh repo edit failed. Sign in with: gh auth login" }
Write-Output "GitHub: homepage of $Repo set to $Url"

git add README.md
git commit -m "Add the live demo link: $Url"
if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
if (-not $NoPush) {
  git push origin main
  if ($LASTEXITCODE -ne 0) { throw "git push failed" }
}
Write-Output "Done."
