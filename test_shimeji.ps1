# test_shimeji.ps1
# Automated Shimeji test harness: kill existing -> clean log -> start -> observe -> analyze -> graceful close
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\test_shimeji.ps1 -DurationSeconds 180
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\test_shimeji.ps1 -DurationSeconds 60 -KeepRunning
param(
    [int]$DurationSeconds = 180,
    [switch]$KeepRunning
)

$ErrorActionPreference = "Continue"
$ShimejiDir = "C:\Users\TCL\Desktop\zhizhiji-final\runtime\shimejiee-local\shimejiee"
$JarPath    = Join-Path $ShimejiDir "Shimeji-ee.jar"
$Log0Path   = Join-Path $ShimejiDir "ShimejieeLog0.log"
$Log1Path   = Join-Path $ShimejiDir "ShimejieeLog1.log"
$BackupDir  = Join-Path $ShimejiDir "log-backups"

Write-Host "== Shimeji Auto Test =="
Write-Host "Dir     : $ShimejiDir"
Write-Host "Jar     : $JarPath"
Write-Host "Duration: $DurationSeconds s"
Write-Host ""

Write-Host "[1/5] Killing existing Shimeji java processes..."
$existing = Get-CimInstance Win32_Process -Filter "Name='javaw.exe' OR Name='java.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -match "Shimeji-ee" }
if ($existing) {
    foreach ($p in $existing) {
        Write-Host ("  kill PID " + $p.ProcessId)
        taskkill.exe /PID $p.ProcessId /F | Out-Null
    }
    Start-Sleep -Seconds 2
} else {
    Write-Host "  no existing Shimeji process"
}
Get-ChildItem -Path $ShimejiDir -Filter "ShimejieeLog*.lck" -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "[2/5] Cleaning old log..."
if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir | Out-Null }
if (Test-Path $Log0Path) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = Join-Path $BackupDir "ShimejieeLog0-$stamp.log"
    Copy-Item $Log0Path $backup -Force
    Write-Host ("  backup to: " + $backup)
    Remove-Item $Log0Path -Force -ErrorAction SilentlyContinue
}
if (Test-Path $Log1Path) { Remove-Item $Log1Path -Force -ErrorAction SilentlyContinue }

Write-Host "[3/5] Starting Shimeji-ee.jar..."
$startTime = Get-Date
$proc = Start-Process -FilePath "javaw.exe" -ArgumentList @("-jar", $JarPath) `
    -WorkingDirectory $ShimejiDir -PassThru
Write-Host ("  PID: " + $proc.Id)
Start-Sleep -Seconds 3
if (Test-Path $Log0Path) {
    Write-Host ("  log generated: " + $Log0Path)
} else {
    Write-Host "  [WARN] log not generated yet"
}

Write-Host ("[4/5] Observing (" + $DurationSeconds + " s)...")
$remaining = $DurationSeconds
while ($remaining -gt 0) {
    if (($remaining % 30) -eq 0) { Write-Host ("  " + $remaining + " s remaining...") }
    Start-Sleep -Seconds 5
    $remaining -= 5
}

Write-Host ""
if (-not $KeepRunning) {
    Write-Host "[5/5] Gracefully closing Shimeji so JVM flushes log buffer..."
    $running = Get-CimInstance Win32_Process -Filter "Name='javaw.exe' OR Name='java.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -match "Shimeji-ee" }
    foreach ($p in $running) { taskkill.exe /PID $p.ProcessId | Out-Null }
    Start-Sleep -Seconds 5
    $stragglers = Get-CimInstance Win32_Process -Filter "Name='javaw.exe' OR Name='java.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -match "Shimeji-ee" }
    foreach ($p in $stragglers) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
}

Write-Host "Analyzing log..."
$logs = @()
if (Test-Path $Log0Path) { $logs += Get-Content $Log0Path -Raw }
if (Test-Path $Log1Path) {
    $log1Info = Get-Item $Log1Path
    if ($log1Info.LastWriteTime -gt $startTime) {
        $logs += Get-Content $Log1Path -Raw
    }
}
$body = [string]::Join("`n", $logs)

function CountMatches($pattern) {
    return ([regex]::Matches($body, $pattern)).Count
}

$mascotCreated = CountMatches "mascot created"
$varEx         = CountMatches "VariableException"
$lostGround    = CountMatches "Lost Ground"
$lgWalkAfterInit  = ([regex]::Matches($body, "Lost Ground.*Move.*Walk")).Count
$lgStayAfterInit  = ([regex]::Matches($body, "Lost Ground.*Stay.*(Greet|Sleep|Eat|Pipi|Laugh)")).Count
$lgScanAfterInit  = ([regex]::Matches($body, "Lost Ground.*ScanMove")).Count
$oob           = CountMatches "Out.*of.*screen.*bounds"
$fallInits     = ([regex]::Matches($body, "init.*Default Behavior.*Fall")).Count

$greetWait   = ([regex]::Matches($body, "Default Behavior.*GreetWait")).Count
$scanGreet   = ([regex]::Matches($body, "Default Behavior.*ScanGreet")).Count
$greetAct    = ([regex]::Matches($body, "Default Behavior.*GreetAct")).Count
$greetReact  = ([regex]::Matches($body, "Default Behavior.*GreetReact")).Count
$laugh       = ([regex]::Matches($body, "Default Behavior.*Behavior\(Laugh\)")).Count

Write-Host ""
Write-Host "====== Test Report ======"
Write-Host ("mascot created           : " + $mascotCreated)
Write-Host ("VariableException        : " + $varEx)
Write-Host ("Total Lost Ground        : " + $lostGround)
Write-Host ("  Walk LG after init     : " + $lgWalkAfterInit)
Write-Host ("  Stay LG after init     : " + $lgStayAfterInit)
Write-Host ("  ScanMove LG after init : " + $lgScanAfterInit)
Write-Host ("Out Of Screen Bounds     : " + $oob)
Write-Host ("Fall inits               : " + $fallInits)
Write-Host ""
Write-Host "Greet interaction stats:"
Write-Host ("  GreetWait  (ham bcast) : " + $greetWait)
Write-Host ("  ScanGreet  (zhi scan)  : " + $scanGreet)
Write-Host ("  GreetAct   (zhi reach) : " + $greetAct)
Write-Host ("  GreetReact (ham clap)  : " + $greetReact)
Write-Host ("  Laugh      (zhi laugh) : " + $laugh)
Write-Host "========================="
Write-Host ""

$anomaly = ($varEx -gt 0) -or ($lgWalkAfterInit -gt 0) -or ($lgStayAfterInit -gt 0) -or ($lgScanAfterInit -gt 0) -or ($oob -gt 0)
if ($anomaly) {
    Write-Host "[FAIL] Found anomaly above. See log for details." -ForegroundColor Red
} elseif ($greetAct -gt 0 -and $greetReact -gt 0) {
    Write-Host "[PASS] Greet interaction triggered, no anomalies." -ForegroundColor Green
} else {
    Write-Host "[PARTIAL] No anomalies, but greet did not complete a full round." -ForegroundColor Yellow
}

if ($KeepRunning) {
    Write-Host "Shimeji still running (PID $($proc.Id))."
} else {
    Write-Host "Shimeji closed. Run again with -KeepRunning to keep it visible after the test."
}
