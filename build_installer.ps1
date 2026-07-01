<#
  GH05T3 Sovereign Stack — One-click build script
  Run from:  PS C:\Users\leer4\GH05T3>  .\build_installer.ps1
#>

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

Write-Host "`n=== GH05T3 Installer Build ===" -ForegroundColor Cyan

# 1. Ensure Python 3.12 is available
$PY = "C:\Users\leer4\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $PY)) {
    $PY = (Get-Command python).Source
}
Write-Host "Python: $PY"

# 2. Install build dependencies into system Python (where supervisor runs from)
Write-Host "`n[1/4] Installing pystray, pillow, pyinstaller..." -ForegroundColor Yellow
& $PY -m pip install --quiet pystray pillow pyinstaller

# 3. Build the EXE
Write-Host "`n[2/4] Building GH05T3-Sovereign.exe..." -ForegroundColor Yellow
Set-Location $ROOT
& $PY -m PyInstaller main.spec --clean --noconfirm

if (-not (Test-Path "$ROOT\dist\GH05T3-Sovereign.exe")) {
    Write-Host "ERROR: EXE not found after build." -ForegroundColor Red
    exit 1
}
Write-Host "EXE built: $ROOT\dist\GH05T3-Sovereign.exe" -ForegroundColor Green

# 4. Create the Inno Setup script
Write-Host "`n[3/4] Writing Inno Setup script..." -ForegroundColor Yellow

$ISS = @"
; GH05T3 Sovereign Stack — Inno Setup installer
; Compile with: iscc sovereign_install.iss
; Download Inno Setup free: https://jrsoftware.org/isinfo.php

#define AppName    "GH05T3 Sovereign Stack"
#define AppVersion "3.0.0"
#define AppExe     "GH05T3-Sovereign.exe"
#define AppRoot    "C:\Users\leer4\GH05T3"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=leerobber
AppPublisherURL=https://aethyro.com
DefaultDirName={autopf}\GH05T3
DefaultGroupName=GH05T3
OutputDir={#AppRoot}\dist
OutputBaseFilename=GH05T3-Sovereign-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=
UninstallDisplayIcon={app}\GH05T3-Sovereign.exe
PrivilegesRequired=lowest
CloseApplications=no
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "Create desktop shortcut";      GroupDescription: "Shortcuts:"; Flags: checkedonce
Name: "startupentry";   Description: "Launch on Windows startup";    GroupDescription: "Startup:";   Flags: unchecked

[Files]
; The compiled EXE (tray host + embedded supervisor launcher)
Source: "{#AppRoot}\dist\GH05T3-Sovereign.exe";   DestDir: "{app}"; Flags: ignoreversion

; Supervisor and runtime scripts (EXE calls these via system Python)
Source: "{#AppRoot}\scripts\runtime\supervisor.py";     DestDir: "{app}\scripts\runtime"; Flags: ignoreversion
Source: "{#AppRoot}\scripts\runtime\tray_v2.py";        DestDir: "{app}\scripts\runtime"; Flags: ignoreversion
Source: "{#AppRoot}\scripts\runtime\serve_frontend.py"; DestDir: "{app}\scripts\runtime"; Flags: ignoreversion
Source: "{#AppRoot}\scripts\runtime\cmd_listener.py";   DestDir: "{app}\scripts\runtime"; Flags: ignoreversion
Source: "{#AppRoot}\scripts\runtime\tunnel_watcher.py"; DestDir: "{app}\scripts\runtime"; Flags: ignoreversion

; Launchers
Source: "{#AppRoot}\run.bat";        DestDir: "{app}"; Flags: ignoreversion
Source: "{#AppRoot}\GHOST.bat";      DestDir: "{app}"; Flags: ignoreversion
Source: "{#AppRoot}\run_stack.py";   DestDir: "{app}"; Flags: ignoreversion

; Frontend build
Source: "{#AppRoot}\frontend\build\*"; DestDir: "{app}\frontend\build"; Flags: ignoreversion recursesubdirs

; Genome Lab dashboard
Source: "{#AppRoot}\frontend\genome_dashboard.html"; DestDir: "{app}\frontend"; Flags: ignoreversion skipifsourcedoesntexist

; SovereignNation surface
Source: "{#AppRoot}\sovereignnation\*"; DestDir: "{app}\sovereignnation"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

; Docs
Source: "{#AppRoot}\README.md";                    DestDir: "{app}"; Flags: ignoreversion
Source: "{#AppRoot}\docs\PROJECT_OVERVIEW.md";     DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
; Desktop shortcut
Name: "{autodesktop}\GH05T3 Sovereign";     Filename: "{app}\GH05T3-Sovereign.exe"; Tasks: desktopicon; Comment: "GH05T3 Sovereign Stack"

; Start Menu
Name: "{group}\GH05T3 Sovereign Stack";     Filename: "{app}\GH05T3-Sovereign.exe"; Comment: "Launch GH05T3 full stack"
Name: "{group}\Open Dashboard";             Filename: "http://localhost:3210"
Name: "{group}\Open Genome Lab";            Filename: "http://localhost:7720/genome_dashboard.html"
Name: "{group}\Open Logs Folder";           Filename: "{app}\logs"
Name: "{group}\Uninstall GH05T3";           Filename: "{uninstallexe}"

; Startup (optional task)
Name: "{userstartup}\GH05T3 Sovereign";     Filename: "{app}\GH05T3-Sovereign.exe"; Tasks: startupentry

[Run]
; Launch after install
Filename: "{app}\GH05T3-Sovereign.exe"; Description: "Launch GH05T3 now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop supervisor on uninstall
Filename: "{app}\GH05T3-Sovereign.exe"; Parameters: "--stop"; RunOnceId: "StopServices"; Flags: nowait

[Code]
// Check prerequisites on install start
function InitializeSetup(): Boolean;
var
  py312: String;
  msg: String;
begin
  Result := True;
  py312 := ExpandConstant('{pf}\Python312\python.exe');

  // Check Python 3.12
  if not FileExists('C:\Users\leer4\AppData\Local\Programs\Python\Python312\python.exe') then
  begin
    msg := 'Python 3.12 was not found at the expected location.' + #13#10 +
           'GH05T3 requires Python 3.12 to run its services.' + #13#10 + #13#10 +
           'Download from: https://python.org/downloads/' + #13#10 + #13#10 +
           'Install Python 3.12 then re-run this installer.' + #13#10 + #13#10 +
           'Continue anyway? (only if you know Python is installed elsewhere)';
    if MsgBox(msg, mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end;
end;
"@

$ISS | Out-File -FilePath "$ROOT\sovereign_install.iss" -Encoding UTF8
Write-Host "Inno Setup script written: $ROOT\sovereign_install.iss" -ForegroundColor Green

# 5. Done — instructions
Write-Host "`n[4/4] Done!" -ForegroundColor Green
Write-Host @"

Next steps:
  1. The EXE is ready at:
        $ROOT\dist\GH05T3-Sovereign.exe
     Double-click it to test — it starts the tray app + full stack.

  2. To build the one-click installer .exe:
     a. Download Inno Setup free from https://jrsoftware.org/isinfo.php
     b. Open sovereign_install.iss in Inno Setup Compiler
     c. Press Ctrl+F9 to compile
     d. Installer will be at: $ROOT\dist\GH05T3-Sovereign-Setup.exe

  3. The installer:
     - Copies all files to Program Files\GH05T3
     - Creates desktop shortcut + Start Menu
     - Optional: adds to Windows startup
     - Launches tray app at end of install
     - Includes one-click uninstaller

"@ -ForegroundColor White