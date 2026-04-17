# watch_greet.ps1 - Tail ShimejieeLog0.log and report greet interaction progress.
# Stops when at least one full GreetAct/GreetReact pair is observed, or when MaxSeconds elapses.
param(
    [int]$MaxSeconds = 600,
    [int]$PollIntervalSec = 5
)

$ErrorActionPreference = "Continue"
$LogPath = "C:\Users\TCL\Desktop\zhizhiji-final\runtime\shimejiee-local\shimejiee\ShimejieeLog0.log"

if (-not (Test-Path $LogPath)) {
    Write-Host "log not found: $LogPath"
    exit 1
}

$startTime  = Get-Date
$lastSeen   = @{ GreetWait=0; ScanGreet=0; GreetAct=0; GreetReact=0; OOB=0; LostGround=0; VarEx=0 }

Write-Host "Watching $LogPath for up to $MaxSeconds s (poll every $PollIntervalSec s)..."
Write-Host ""

while ($true) {
    $elapsed = ((Get-Date) - $startTime).TotalSeconds
    if ($elapsed -gt $MaxSeconds) {
        Write-Host "[TIMEOUT] reached MaxSeconds=$MaxSeconds, stopping watch."
        break
    }

    if (Test-Path $LogPath) {
        $body = Get-Content $LogPath -Raw -ErrorAction SilentlyContinue
        if (-not $body) { $body = "" }

        $cur = @{
            GreetWait   = ([regex]::Matches($body, "Default Behavior.*GreetWait")).Count
            ScanGreet   = ([regex]::Matches($body, "Default Behavior.*ScanGreet")).Count
            GreetAct    = ([regex]::Matches($body, "Default Behavior.*GreetAct")).Count
            GreetReact  = ([regex]::Matches($body, "Default Behavior.*GreetReact")).Count
            OOB         = ([regex]::Matches($body, "Out.*of.*screen.*bounds")).Count
            LostGround  = ([regex]::Matches($body, "Lost Ground")).Count
            VarEx       = ([regex]::Matches($body, "VariableException")).Count
        }

        $deltas = @()
        foreach ($k in @("GreetWait","ScanGreet","GreetAct","GreetReact","OOB","LostGround","VarEx")) {
            if ($cur[$k] -ne $lastSeen[$k]) {
                $deltas += ("{0}: {1}->{2}" -f $k, $lastSeen[$k], $cur[$k])
                $lastSeen[$k] = $cur[$k]
            }
        }

        $ts = Get-Date -Format "HH:mm:ss"
        if ($deltas.Count -gt 0) {
            Write-Host ("[{0}] +{1}s  {2}" -f $ts, [int]$elapsed, ($deltas -join "  |  "))
        } else {
            Write-Host ("[{0}] +{1}s  no change  (GW={2} SG={3} GA={4} GR={5} OOB={6})" -f `
                $ts, [int]$elapsed, $cur.GreetWait, $cur.ScanGreet, $cur.GreetAct, $cur.GreetReact, $cur.OOB)
        }

        if ($cur.GreetAct -ge 1 -and $cur.GreetReact -ge 1) {
            Write-Host ""
            Write-Host "[PASS] full greet round detected: GreetAct=$($cur.GreetAct)  GreetReact=$($cur.GreetReact)"
            Write-Host "        (GreetWait=$($cur.GreetWait)  ScanGreet=$($cur.ScanGreet))"
            Write-Host "        anomalies: OOB=$($cur.OOB)  LostGround=$($cur.LostGround)  VarEx=$($cur.VarEx)"
            break
        }
    } else {
        Write-Host "[WARN] log missing, shimeji may have died"
    }

    Start-Sleep -Seconds $PollIntervalSec
}
