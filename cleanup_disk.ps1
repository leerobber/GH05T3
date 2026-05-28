# cleanup_disk.ps1
# Safe disk cleanup for C: drive
# Review each section — comment out any you want to skip
# Run from PowerShell as normal user (no admin needed for user folders)
#
# ESTIMATED SAVINGS: ~120-170 GB

Write-Host "=== GH05T3 / SovereignNation Disk Cleanup ===" -ForegroundColor Cyan
Write-Host ""

function Remove-SafeItem($path, $label) {
    if (Test-Path $path) {
        $sz = (Get-ChildItem $path -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $gb = [math]::Round($sz / 1GB, 2)
        Write-Host "  Deleting $label ($gb GB)..." -ForegroundColor Yellow
        Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  Freed $gb GB ✓" -ForegroundColor Green
    } else {
        Write-Host "  SKIP (not found): $label" -ForegroundColor DarkGray
    }
}

# ============================================================
# SECTION 1: HuggingFace Cache — Stable Diffusion models
# These are image-gen models, not used by economy or GH05T3
# Savings: ~58 GB
# ============================================================
Write-Host "[1] Stable Diffusion models (not used by economy/GH05T3)" -ForegroundColor Magenta
$HF = "C:\Users\leer4\.cache\huggingface\hub"
Remove-SafeItem "$HF\models--Lykon--dreamshaper-xl-1-0"      "DreamShaper XL (27.8 GB)"
Remove-SafeItem "$HF\models--SimianLuo--LCM_Dreamshaper_v7"  "LCM DreamShaper v7 (11 GB)"
Remove-SafeItem "$HF\models--emilianJR--epiCRealism"          "epiCRealism (8.5 GB)"
Remove-SafeItem "$HF\models--runwayml--stable-diffusion-v1-5" "SD v1-5 runwayml (11 GB)"
Remove-SafeItem "$HF\models--stable-diffusion-v1-5--stable-diffusion-v1-5" "SD v1-5 alt (empty)"
Remove-SafeItem "$HF\models--gsdf--Counterfeit-V3.0"          "Counterfeit V3 (empty)"

# ============================================================
# SECTION 2: Old Qwen2 (pre-2.5) — superseded, in Ollama already
# Savings: ~37 GB
# ============================================================
Write-Host ""
Write-Host "[2] Old Qwen2 base models (superseded by Qwen2.5 + in Ollama)" -ForegroundColor Magenta
Remove-SafeItem "$HF\models--Qwen--Qwen2-1.5B-Instruct"  "Qwen2 1.5B (old) (6.2 GB)"
Remove-SafeItem "$HF\models--Qwen--Qwen2-7B-Instruct"    "Qwen2 7B (old) (30.5 GB)"

# ============================================================
# SECTION 3: Qwen2.5 HF cache duplicates
# Already stored as GGUFs in Ollama — HF cache versions redundant
# Savings: ~37 GB
# ============================================================
Write-Host ""
Write-Host "[3] Qwen2.5 HF cache (already in Ollama as GGUF — duplicates)" -ForegroundColor Magenta
Remove-SafeItem "$HF\models--Qwen--Qwen2.5-1.5B-Instruct" "Qwen2.5 1.5B HF cache (6.2 GB)"
Remove-SafeItem "$HF\models--Qwen--Qwen2.5-7B-Instruct"   "Qwen2.5 7B HF cache (30.5 GB)"

# ============================================================
# SECTION 4: Phi-2 — not used in current stack
# Savings: ~11 GB
# ============================================================
Write-Host ""
Write-Host "[4] Microsoft Phi-2 (not in current stack)" -ForegroundColor Magenta
Remove-SafeItem "$HF\models--microsoft--phi-2" "Phi-2 (11.1 GB)"

# ============================================================
# SECTION 5: pip cache — always safe to clear
# pip re-downloads packages when needed
# Savings: ~18 GB
# ============================================================
Write-Host ""
Write-Host "[5] pip download cache (safe to clear — re-downloads as needed)" -ForegroundColor Magenta
Remove-SafeItem "C:\Users\leer4\AppData\Local\pip\cache" "pip cache (18.6 GB)"

# ============================================================
# SECTION 6: Puppeteer cache — headless Chrome, probably unused
# Savings: ~6.9 GB
# ============================================================
Write-Host ""
Write-Host "[6] Puppeteer (headless Chrome cache — not used by economy/GH05T3)" -ForegroundColor Magenta
Remove-SafeItem "C:\Users\leer4\.cache\puppeteer" "Puppeteer cache (6.9 GB)"

# ============================================================
# SECTION 7: Windows Temp folder
# Savings: ~7 GB
# ============================================================
Write-Host ""
Write-Host "[7] Windows/User Temp files" -ForegroundColor Magenta
Write-Host "  Cleaning Temp..." -ForegroundColor Yellow
Get-ChildItem "C:\Users\leer4\AppData\Local\Temp" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  Temp cleaned ✓" -ForegroundColor Green

# ============================================================
# SECTION 8: Downloads — duplicate installers only
# Savings: ~3.8 GB
# ============================================================
Write-Host ""
Write-Host "[8] Downloads — duplicate and old installers" -ForegroundColor Magenta
$DL = "C:\Users\leer4\Downloads"
$dupes = @(
    "Kai-2.5.0-windows (1).msi",
    "WindsurfUserSetup-x64-1.9600.41 (1).exe",
    "NVIDIA_app_v11.0.7.247 (1).exe",
    "Claude Setup (2).exe",
    "Claude Setup (4).exe",
    "Claude Setup (5).exe",
    "Claude Setup (1).exe",
    "Claude Setup (3).exe",
    "OpenJDK25U-jdk_x64_windows_hotspot_25.0.2_10 (1).msi",
    "diffgram-master_1.zip",
    "s2s-v1.5.0.zip",
    "satisfiable-ai-v0.1.0.zip",
    "gh05t3-fine-tune-2xt4 (1).ipynb",
    "termux_mcp_server_1.py",
    "termux_mcp_server_2.py",
    "codeql-sarif-results (1).zip",
    "veritas-v0.1.1.zip",
    "pascal-voc-v2.2.6.zip",
    "epub-and-vtt-to-llm-1.0.0.zip",
    "gh05t3_sovereign_1.zip",
    "Kai-2.4.1-windows.msi",
    "GitHubDesktopSetup-x64.exe",
    "CursorUserSetup-x64-2.6.19.exe",
    "NVIDIA_app_v11.0.7.247.exe",
    "codeql-bundle-linux64.tar.gz",
    "oss-sources-service-container-x86_64.tgz",
    "codeql-bundle-win64.tar.gz"
)
$saved = 0
foreach ($f in $dupes) {
    $fp = Join-Path $DL $f
    if (Test-Path $fp) {
        $sz = (Get-Item $fp).Length
        $saved += $sz
        Remove-Item $fp -Force -ErrorAction SilentlyContinue
        Write-Host "  Deleted: $f ($([math]::Round($sz/1MB,1)) MB)" -ForegroundColor Green
    }
}
Write-Host "  Downloads freed: $([math]::Round($saved/1GB,2)) GB" -ForegroundColor Green

# ============================================================
# FINAL REPORT
# ============================================================
Write-Host ""
Write-Host "=== CLEANUP COMPLETE ===" -ForegroundColor Cyan
$drive = Get-PSDrive C
$freeGB = [math]::Round($drive.Free / 1GB, 2)
Write-Host "C: drive free space now: $freeGB GB" -ForegroundColor White
Write-Host ""
Write-Host "Files KEPT (valuable for SovereignNation/economy):" -ForegroundColor Cyan
Write-Host "  .cache/huggingface/hub/models--tastytator--*  (all LoRA weights)"
Write-Host "  .cache/huggingface/hub/models--BAAI--bge-large-en-v1.5  (embeddings)"
Write-Host "  .cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2  (embeddings)"
Write-Host "  .cache/huggingface/hub/models--amd--Llama-3.2-3B-Instruct-onnx-ryzenai-1.7-hybrid  (NPU!)"
Write-Host "  .cache/codex-runtimes/  (keep)"
Write-Host ""
Write-Host "Ready to quantize Avery? Run: python C:\Users\leer4\GH05T3\download_avery_q4km.py"
Write-Host "(after running kaggle_quantize_avery.ipynb first)"
