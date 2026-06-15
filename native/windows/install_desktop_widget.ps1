$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$Shell = New-Object -ComObject WScript.Shell

function New-Shortcut {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Target,
        [string]$Arguments = "",
        [string]$WorkingDirectory = $Root,
        [string]$IconLocation = ""
    )

    $Shortcut = $Shell.CreateShortcut($Path)
    $Shortcut.TargetPath = $Target
    $Shortcut.Arguments = $Arguments
    $Shortcut.WorkingDirectory = $WorkingDirectory
    if ($IconLocation) {
        $Shortcut.IconLocation = $IconLocation
    }
    $Shortcut.Save()
}

$WidgetPath = Join-Path $Root "GH05T3_Widget.hta"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $Root)
$RunPath = Join-Path $RepoRoot "run.bat"

New-Shortcut `
    -Path (Join-Path $Desktop "GH05T3 Widget.lnk") `
    -Target "$env:WINDIR\System32\mshta.exe" `
    -Arguments "`"$WidgetPath`"" `
    -IconLocation "$env:WINDIR\System32\shell32.dll,13"

New-Shortcut `
    -Path (Join-Path $Desktop "GH05T3 App.lnk") `
    -Target $RunPath `
    -WorkingDirectory $RepoRoot `
    -IconLocation "$env:WINDIR\System32\shell32.dll,13"

New-Shortcut `
    -Path (Join-Path $Desktop "Open GH05T3 Webapp.lnk") `
    -Target "$env:WINDIR\System32\cmd.exe" `
    -Arguments '/c start "" "http://localhost:3210"' `
    -WorkingDirectory $Root `
    -IconLocation "$env:WINDIR\System32\shell32.dll,220"

Write-Host "Installed Desktop shortcuts:"
Write-Host " - GH05T3 Widget"
Write-Host " - GH05T3 App"
Write-Host " - Open GH05T3 Webapp"
