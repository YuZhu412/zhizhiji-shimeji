# watch_and_sync.ps1
# 自动监听 zhizhiji-shimeji GitHub 仓库更新，同步文件到本地 Shimeji-ee 目录
# 用法：在 PowerShell 中运行此脚本（需要已安装 Git）
#   .\watch_and_sync.ps1
# 可选参数：
#   -RepoDir     本地仓库路径（默认：脚本所在目录）
#   -ShimejiDir  Shimeji-ee 的 img 目录路径（需要手动设置）
#   -Interval    检查间隔秒数（默认：60）

param(
    [string]$RepoDir   = $PSScriptRoot,
    [string]$ShimejiDir = "C:\Users\TCL\Desktop\zhizhiji-final\runtime\shimejiee-local\shimejiee\img",   # ← 已设为本机路径
    [int]   $Interval  = 60
)

# ── 检查路径 ─────────────────────────────────────────────────
if (-not (Test-Path $RepoDir)) {
    Write-Error "仓库目录不存在：$RepoDir"
    exit 1
}
if (-not (Test-Path $ShimejiDir)) {
    Write-Warning "Shimeji img 目录不存在：$ShimejiDir"
    Write-Warning "请修改脚本顶部的 -ShimejiDir 参数后重试"
    exit 1
}

$CharNames = @("Zhizhiji", "ham")   # 要同步的角色列表

Write-Host "🐭 吱吱 Shimeji 自动同步启动！" -ForegroundColor Cyan
Write-Host "   仓库目录：$RepoDir"
Write-Host "   Shimeji img 目录：$ShimejiDir"
Write-Host "   检查间隔：$Interval 秒"
Write-Host "   按 Ctrl+C 停止`n"

# 记录当前 commit hash
Push-Location $RepoDir
$lastHash = (git rev-parse HEAD 2>$null).Trim()
Pop-Location

function Sync-ToShimeji {
    param([string]$RepoDir, [string]$ShimejiDir, [string[]]$CharNames)

    foreach ($char in $CharNames) {
        $srcImg  = Join-Path $RepoDir "runtime\shimejiee-local\shimejiee\img\$char"
        $dstImg  = Join-Path $ShimejiDir $char

        if (-not (Test-Path $srcImg)) { continue }

        # 同步图片帧（PNG 文件）
        $pngFiles = Get-ChildItem $srcImg -Filter "*.png" -ErrorAction SilentlyContinue
        foreach ($png in $pngFiles) {
            $dst = Join-Path $dstImg $png.Name
            if (-not (Test-Path $dstImg)) { New-Item -ItemType Directory -Path $dstImg | Out-Null }
            Copy-Item $png.FullName $dst -Force
        }

        # 同步 conf 目录（actions.xml / behaviors.xml）
        $srcConf = Join-Path $srcImg "conf"
        $dstConf = Join-Path $dstImg "conf"
        if (Test-Path $srcConf) {
            if (-not (Test-Path $dstConf)) { New-Item -ItemType Directory -Path $dstConf | Out-Null }
            Copy-Item "$srcConf\*.xml" $dstConf -Force
        }

        Write-Host "   ✅ 已同步角色：$char" -ForegroundColor Green
    }
}

# ── 主循环 ────────────────────────────────────────────────────
while ($true) {
    Start-Sleep -Seconds $Interval

    Push-Location $RepoDir
    git fetch origin main --quiet 2>$null
    $remoteHash = (git rev-parse origin/main 2>$null).Trim()
    Pop-Location

    if ($remoteHash -and $remoteHash -ne $lastHash) {
        Write-Host "`n$(Get-Date -Format 'HH:mm:ss') 🔄 检测到新更新！正在同步..." -ForegroundColor Yellow

        Push-Location $RepoDir
        git pull origin main --quiet 2>$null
        $lastHash = (git rev-parse HEAD 2>$null).Trim()
        Pop-Location

        Sync-ToShimeji -RepoDir $RepoDir -ShimejiDir $ShimejiDir -CharNames $CharNames

        # 系统通知
        $msg = "吱吱桌面宠物有新形象啦！请手动重启 Shimeji-ee.jar 生效 🐭"
        Add-Type -AssemblyName System.Windows.Forms
        $notify = New-Object System.Windows.Forms.NotifyIcon
        $notify.Icon = [System.Drawing.SystemIcons]::Information
        $notify.BalloonTipTitle = "吱吱 Shimeji 已更新"
        $notify.BalloonTipText  = $msg
        $notify.Visible = $true
        $notify.ShowBalloonTip(8000)
        Start-Sleep -Seconds 9
        $notify.Dispose()

        Write-Host "   💬 通知已发送，请手动重启 Shimeji-ee.jar" -ForegroundColor Magenta
    } else {
        Write-Host "$(Get-Date -Format 'HH:mm:ss') 无更新" -ForegroundColor DarkGray
    }
}
