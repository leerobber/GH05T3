# Helper for Windows PowerShell users to set Pact Broker env vars for local script testing.
# Usage:
#   .\scripts\set-pact-env.ps1
#   python scripts\publish_pacts.py pacts\ (git rev-parse HEAD) ci

$env:PACT_BROKER_BASE_URL = "https://your-org.pactflow.io"
$env:PACT_BROKER_TOKEN = "your-api-token-here"

Write-Host "PACT_BROKER_BASE_URL and PACT_BROKER_TOKEN set for this PowerShell session."
Write-Host "Run your pact scripts now (e.g. python scripts\publish_pacts.py ...)"
Write-Host "Note: These are only for the current terminal session. Use GitHub Secrets for CI."