# demo_on_helper.ps1 - called by DEMO_ON.bat
# Kills stray Ollama-competing Python processes that aren't supervisor-managed

$managedPids = @()
try {
    $status = Invoke-WebRequest -Uri "http://localhost:8090/status" -TimeoutSec 4 -UseBasicParsing
    $data = $status.Content | ConvertFrom-Json
    $managedPids = $data.services.PSObject.Properties.Value.pid | Where-Object { $_ -gt 0 }
} catch {
    Write-Host "  [warn] Supervisor not reachable - will kill all matching strays"
}

$targets = @('continuous_learner.py', 'amplifier.py', 'cmd_listener.py', 'ghost_trainer.py')
$killed = 0

Get-WmiObject Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
    $cli = $_.CommandLine
    $procId = $_.ProcessId
    foreach ($t in $targets) {
        if ($cli -like "*$t*" -and $managedPids -notcontains $procId) {
            try {
                Stop-Process -Id $procId -Force -ErrorAction Stop
                Write-Host "  Stopped stray: $t (PID $procId)"
                $killed++
            } catch {
                Write-Host "  Skip PID $procId (already gone)"
            }
        }
    }
}

Write-Host "  Stray processes killed: $killed"

# Check proxy health
try {
    $h = Invoke-WebRequest -Uri "http://localhost:7861/health" -TimeoutSec 5 -UseBasicParsing
    $hdata = $h.Content | ConvertFrom-Json
    Write-Host "  [3/3] Proxy OK - ollama=$($hdata.ollama)  modules=$($hdata.models.Count)"
} catch {
    Write-Host "  [3/3] Proxy not responding - ensure supervisor is running"
}
