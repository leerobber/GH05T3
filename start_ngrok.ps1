#Requires -Version 5.1
<#
.SYNOPSIS
  Start ngrok tunnel for GH05T3 gateway (port 8002).

.DESCRIPTION
  Used by Windows Terminal session restore and manual public access.
  Tunnel name "aethyro-gateway" is defined in %LOCALAPPDATA%\ngrok\ngrok.yml.
  Logs the public URL to ngrok_startup.log and tunnel_url.txt.

  Alternative (no ngrok): supervisor.py already runs cloudflared tunnels —
  see data/tunnel_urls.json for trycloudflare.com URLs.
#>
param(
    [int]$Port = 8002,
    [string]$TunnelName = "aethyro-gateway"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogFile = Join-Path $Root "ngrok_startup.log"
$UrlFile = Join-Path $Root "tunnel_url.txt"

function Write-Log([string]$Msg) {
    $line = "$(Get-Date -Format 'MM/dd/yyyy HH:mm:ss') - $Msg"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

$ngrok = Get-Command ngrok -ErrorAction SilentlyContinue
if (-not $ngrok) {
    Write-Log "ngrok not found on PATH. Install: winget install ngrok.ngrok"
    exit 1
}

function Get-GatewayUrl {
    try {
        $resp = Invoke-RestMethod "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 3
        $hit = $resp.tunnels |
            Where-Object { $_.public_url -and ($_.config.addr -match ":$Port\b") } |
            Select-Object -First 1
        if ($hit) { return $hit.public_url }
        $https = $resp.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1
        if ($https) { return $https.public_url }
    } catch {}
    return $null
}

$existing = Get-GatewayUrl
if ($existing) {
    Write-Log "ngrok already running: $existing"
    Set-Content -Path $UrlFile -Value $existing -Encoding ASCII -NoNewline
    while ($true) { Start-Sleep -Seconds 120 }
}

Write-Log "Starting ngrok tunnel '$TunnelName' -> localhost:$Port ..."
$proc = Start-Process -FilePath $ngrok.Source `
    -ArgumentList @("start", $TunnelName, "--log=stdout") `
    -WorkingDirectory $Root -WindowStyle Hidden -PassThru

$deadline = (Get-Date).AddSeconds(45)
$url = $null
while ((Get-Date) -lt $deadline) {
    $url = Get-GatewayUrl
    if ($url) { break }
    if ($proc.HasExited) { break }
    Start-Sleep -Seconds 1
}

if ($url) {
    Write-Log "ngrok started: $url"
    Set-Content -Path $UrlFile -Value $url -Encoding ASCII -NoNewline
} else {
    Write-Log "ngrok process started but public URL not detected (check http://127.0.0.1:4040)"
    if ($proc.HasExited) { exit $proc.ExitCode }
}

Wait-Process -Id $proc.Id