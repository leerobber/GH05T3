; GH05T3 Sovereign Stack — NSIS Installer Script
; Compile: makensis sovereign_install.nsi

Unicode True

!define APP_NAME    "GH05T3 Sovereign Stack"
!define APP_VERSION "3.0.0"
!define APP_EXE     "GH05T3-Sovereign.exe"
!define APP_ROOT    "C:\Users\leer4\GH05T3"
!define INSTALL_DIR "$PROGRAMFILES64\GH05T3"
!define PUBLISHER   "Aethyro / leerobber"
!define APP_URL     "https://aethyro.com"

; --- Compressor ---
SetCompressor /SOLID lzma

; --- Installer metadata ---
Name            "${APP_NAME}"
OutFile         "${APP_ROOT}\dist\GH05T3-Sovereign-Setup.exe"
InstallDir      "${INSTALL_DIR}"
InstallDirRegKey HKCU "Software\GH05T3" "InstallDir"
RequestExecutionLevel user
BrandingText    "${APP_NAME} v${APP_VERSION}"

; --- Modern UI ---
!include "MUI2.nsh"
!include "LogicLib.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON   "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; -----------------------------------------------------------------------
Section "Main" SecMain

  SetOutPath "$INSTDIR"

  ; Core EXE
  File "${APP_ROOT}\dist\${APP_EXE}"

  ; Runtime scripts
  SetOutPath "$INSTDIR\scripts\runtime"
  File "${APP_ROOT}\scripts\runtime\supervisor.py"
  File "${APP_ROOT}\scripts\runtime\tray_v2.py"
  File "${APP_ROOT}\scripts\runtime\serve_frontend.py"
  File "${APP_ROOT}\scripts\runtime\cmd_listener.py"
  File /nonfatal "${APP_ROOT}\scripts\runtime\tunnel_watcher.py"

  ; Launchers
  SetOutPath "$INSTDIR"
  File "${APP_ROOT}\run.bat"
  File /nonfatal "${APP_ROOT}\GHOST.bat"
  File "${APP_ROOT}\run_stack.py"
  File "${APP_ROOT}\README.md"

  ; Frontend build
  SetOutPath "$INSTDIR\frontend\build"
  File /r "${APP_ROOT}\frontend\build\*"

  ; Frontend extras
  SetOutPath "$INSTDIR\frontend"
  File /nonfatal "${APP_ROOT}\frontend\genome_dashboard.html"

  ; SovereignNation layer
  SetOutPath "$INSTDIR\sovereignnation"
  File /nonfatal /r "${APP_ROOT}\sovereignnation\*"

  ; Docs
  SetOutPath "$INSTDIR\docs"
  File /nonfatal "${APP_ROOT}\docs\PROJECT_OVERVIEW.md"

  ; Registry for uninstaller
  WriteRegStr   HKCU "Software\GH05T3" "InstallDir" "$INSTDIR"
  WriteRegStr   HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GH05T3" \
                "DisplayName" "${APP_NAME}"
  WriteRegStr   HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GH05T3" \
                "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr   HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GH05T3" \
                "DisplayVersion" "${APP_VERSION}"
  WriteRegStr   HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GH05T3" \
                "Publisher" "${PUBLISHER}"
  WriteRegStr   HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GH05T3" \
                "URLInfoAbout" "${APP_URL}"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GH05T3" \
                "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GH05T3" \
                "NoRepair" 1

  ; Write uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Desktop shortcut
  CreateShortcut "$DESKTOP\GH05T3 Sovereign.lnk" \
    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0 SW_SHOWNORMAL \
    "" "Launch GH05T3 Sovereign Stack"

  ; Start Menu
  CreateDirectory "$SMPROGRAMS\GH05T3 Sovereign Stack"
  CreateShortcut  "$SMPROGRAMS\GH05T3 Sovereign Stack\GH05T3 Sovereign.lnk" \
    "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  CreateShortcut  "$SMPROGRAMS\GH05T3 Sovereign Stack\Open Dashboard.lnk" \
    "http://localhost:3210"
  CreateShortcut  "$SMPROGRAMS\GH05T3 Sovereign Stack\Open Genome Lab.lnk" \
    "http://localhost:7720/genome_dashboard.html"
  CreateShortcut  "$SMPROGRAMS\GH05T3 Sovereign Stack\Uninstall.lnk" \
    "$INSTDIR\Uninstall.exe"

  ; Launch app after install
  Exec '"$INSTDIR\${APP_EXE}"'

SectionEnd

; -----------------------------------------------------------------------
Section "Uninstall"

  ; Stop the tray app first
  ExecWait '"$INSTDIR\${APP_EXE}" --stop'

  ; Remove files
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\Uninstall.exe"
  Delete "$INSTDIR\run.bat"
  Delete "$INSTDIR\GHOST.bat"
  Delete "$INSTDIR\run_stack.py"
  Delete "$INSTDIR\README.md"
  RMDir  /r "$INSTDIR\scripts"
  RMDir  /r "$INSTDIR\frontend"
  RMDir  /r "$INSTDIR\sovereignnation"
  RMDir  /r "$INSTDIR\docs"
  RMDir  "$INSTDIR"

  ; Shortcuts
  Delete "$DESKTOP\GH05T3 Sovereign.lnk"
  RMDir  /r "$SMPROGRAMS\GH05T3 Sovereign Stack"

  ; Registry
  DeleteRegKey HKCU "Software\GH05T3"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\GH05T3"

SectionEnd
