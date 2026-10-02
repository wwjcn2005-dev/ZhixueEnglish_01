<#
  智学英语 · 手机测试环境一键启动（开发便利工具）

  用法：
      cd D:\ZhixueEnglish
      .\start\_test.ps1

  它只做三件事：
      1) 检查项目正式文件是否齐全
      2) 确认 Web 服务是否已在运行；未运行则用项目真实入口启动（独立窗口）
      3) 检查 adb / Android 真机，并给出手机访问地址

  边界（不改变任何正式业务）：
      * 不改业务代码、不改数据库、不改 learning/ 冻结服务
      * 不改 Android applicationId / WebView 地址 / 端口配置
      * 不安装任何东西，不建虚拟环境，不改系统环境变量，不需要管理员权限
#>
[CmdletBinding()]
param(
    # 默认从 web/app.py 读取真实端口；仅在需要临时换端口时手工指定
    [int]$Port = 0,
    # 只检查、不启动服务
    [switch]$NoStart
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- 路径（基于脚本位置，任何当前目录都可运行）
$ProjectRoot  = Split-Path -Parent $PSScriptRoot
$AppPath      = Join-Path $ProjectRoot 'web\app.py'
$LearningDb   = Join-Path $ProjectRoot 'structured\learning\learning.db'
$ContentPack  = Join-Path $ProjectRoot 'structured\contentpack\v5\FLTRP-EN-7A-2022CUR.sqlite'
$GradleProps  = Join-Path $ProjectRoot 'android\gradle.properties'

# ---------------------------------------------------------------- 小工具
function Write-Step([string]$n, [string]$text) {
    Write-Host ("[$n/4] " + $text) -ForegroundColor Cyan
}
function Write-Ok([string]$text)   { Write-Host ("  " + $text) -ForegroundColor Green }
function Write-Warn([string]$text) { Write-Host ("  " + $text) -ForegroundColor Yellow }
function Write-Info([string]$text) { Write-Host ("  " + $text) -ForegroundColor Gray }

function Get-ConfigInt([string]$file, [string]$pattern) {
    if (-not (Test-Path -LiteralPath $file)) { return $null }
    try {
        $m = Select-String -LiteralPath $file -Pattern $pattern -ErrorAction Stop | Select-Object -First 1
        if ($m) { return [int]$m.Matches[0].Groups[1].Value }
    } catch { }
    return $null
}

function Get-ConfigText([string]$file, [string]$pattern) {
    if (-not (Test-Path -LiteralPath $file)) { return $null }
    try {
        $m = Select-String -LiteralPath $file -Pattern $pattern -ErrorAction Stop | Select-Object -First 1
        if ($m) { return $m.Matches[0].Groups[1].Value }
    } catch { }
    return $null
}

function Test-WebHealth([int]$p) {
    try {
        $r = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/health" -f $p) -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200 -and $r.Content -match '"status"\s*:\s*"ok"')
    } catch {
        return $false
    }
}

function Test-PortBusy([int]$p) {
    try {
        $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction Stop
        return ($null -ne $c)
    } catch {
        return $false
    }
}

function Get-LanIpv4 {
    # 取本机真实局域网 IPv4：排除回环/自动私有地址与常见虚拟网卡
    $virtual = 'vEthernet|WSL|Hyper-V|Default Switch|VMware|VirtualBox|Loopback|Bluetooth|Tailscale|ZeroTier'
    $cands = @()
    try {
        $cands = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
            ForEach-Object { [pscustomobject]@{ IP = $_.IPAddress; Alias = $_.InterfaceAlias } }
    } catch {
        # 退化方案：解析 ipconfig
        $adapter = ''
        foreach ($line in (ipconfig | Out-String) -split "`r?`n") {
            if ($line -match '^[^\s].*:$') { $adapter = $line.TrimEnd(':') }
            elseif ($line -match 'IPv4.*?:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)') {
                $cands += [pscustomobject]@{ IP = $Matches[1]; Alias = $adapter }
            }
        }
    }
    return ($cands | Where-Object { $_.Alias -notmatch $virtual })
}

function Get-AdbPath {
    $c = Get-Command adb -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { return $c.Source }
    $cands = @()
    if ($env:ANDROID_HOME)     { $cands += (Join-Path $env:ANDROID_HOME 'platform-tools\adb.exe') }
    if ($env:ANDROID_SDK_ROOT) { $cands += (Join-Path $env:ANDROID_SDK_ROOT 'platform-tools\adb.exe') }
    if ($env:LOCALAPPDATA)     { $cands += (Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe') }
    $cands += 'G:\AndroidSDK\platform-tools\adb.exe'      # 本机实际 SDK 位置（兜底）
    foreach ($p in $cands) {
        if ($p -and (Test-Path -LiteralPath $p)) { return (Resolve-Path -LiteralPath $p).Path }
    }
    return $null
}

# ---------------------------------------------------------------- 读取项目真实配置
$configPort = Get-ConfigInt $AppPath 'DEFAULT_PORT\s*=\s*(\d+)'
if ($Port -le 0) { $Port = if ($configPort) { $configPort } else { 8770 } }
$portSource = if ($configPort) { 'web/app.py 的 DEFAULT_PORT' } else { '默认值（未能从 web/app.py 读到）' }

$androidUrl = Get-ConfigText $GradleProps 'zhixue\.webBaseUrl\s*=\s*(\S+)'
$androidHost = $null
$androidPort = $null
if ($androidUrl -and $androidUrl -match '^https?://([^:/]+)(?::(\d+))?') {
    $androidHost = $Matches[1]
    if ($Matches[2]) { $androidPort = [int]$Matches[2] }
}

# ---------------------------------------------------------------- [1/4] 检查项目
Write-Step 1 '检查项目'
Write-Info ("项目目录：{0}" -f $ProjectRoot)
$missing = @()
foreach ($pair in @(@($AppPath, 'Web 入口 web/app.py'),
                    @($LearningDb, '正式学习库 structured/learning/learning.db'),
                    @($ContentPack, '正式 contentpack v5'))) {
    if (Test-Path -LiteralPath $pair[0]) { Write-Ok ("找到 " + $pair[1]) }
    else { Write-Warn ("缺少 " + $pair[1] + "：" + $pair[0]); $missing += $pair[1] }
}
$python = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1)
if ($python) { Write-Ok ("Python：" + $python.Source) }
else { Write-Warn '未找到 python 命令（无法自动启动 Web 服务）' }
Write-Info ("端口：{0}（来源：{1}）" -f $Port, $portSource)

# ---------------------------------------------------------------- [2/4] 检查 Web 服务
Write-Step 2 '检查 Web 服务'
$webOk = Test-WebHealth $Port
$webNote = ''
if ($webOk) {
    Write-Ok ("Web 服务已运行（端口 {0}，未启动第二个实例）" -f $Port)
} elseif (Test-PortBusy $Port) {
    Write-Warn ("端口 {0} 已被其他进程占用，且 /health 无响应 → 未启动新实例" -f $Port)
    $webNote = '端口被占用'
} elseif ($NoStart) {
    Write-Warn 'Web 服务未运行（-NoStart 指定只检查）'
    $webNote = '未启动（-NoStart）'
} elseif (-not $python) {
    Write-Warn 'Web 服务未运行，且找不到 python，无法自动启动'
    $webNote = '未找到 python'
} else {
    Write-Info ("正在启动：python web\app.py --host 0.0.0.0 --port {0}" -f $Port)
    $argLine = "& '{0}' '{1}' --host 0.0.0.0 --port {2}" -f $python.Source, $AppPath, $Port
    Start-Process -FilePath 'powershell.exe' `
                  -ArgumentList @('-NoExit', '-NoProfile', '-Command', $argLine) `
                  -WorkingDirectory $ProjectRoot | Out-Null
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Seconds 1
        if (Test-WebHealth $Port) { $webOk = $true; break }
    }
    if ($webOk) { Write-Ok ("Web 服务已启动（独立窗口运行，端口 {0}）" -f $Port) }
    else { Write-Warn '已发起启动，但 25 秒内 /health 仍无响应'; $webNote = '/health 未就绪' }
}
if ($webOk) {
    try {
        $h = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/health" -f $Port) -UseBasicParsing -TimeoutSec 3
        Write-Ok ("/health 返回：" + $h.Content.Trim())
    } catch { }
}

# ---------------------------------------------------------------- [3/4] 检查 Android 测试环境
Write-Step 3 '检查 Android 测试环境'
$adb = Get-AdbPath
$deviceLines = @()
$hasPhone = $false
$s24 = $false
if (-not $adb) {
    Write-Warn '未找到 adb（不影响 Web 测试服务）'
} else {
    Write-Ok ("adb：" + $adb)
    try {
        $out = & $adb devices 2>&1
        foreach ($line in $out) {
            if ($line -match '^(\S+)\s+device$') { $deviceLines += $Matches[1] }
        }
    } catch {
        Write-Warn ('adb devices 执行失败：' + $_.Exception.Message)
    }
    if ($deviceLines.Count -eq 0) {
        Write-Warn '未检测到 Android 真机；Web 测试服务仍已启动。'
        Write-Info '可以打开 Android Studio，连接手机后点 Run。'
    } else {
        $hasPhone = $true
        foreach ($serial in $deviceLines) {
            $model = ''
            $rel = ''
            try { $model = (& $adb -s $serial shell getprop ro.product.model 2>&1 | Out-String).Trim() } catch { }
            try { $rel = (& $adb -s $serial shell getprop ro.build.version.release 2>&1 | Out-String).Trim() } catch { }
            if ($model -match 'SM-S92|SM-S9|S24') { $s24 = $true }
            Write-Ok ("设备：{0} （序列号 {1}，Android {2}）" -f $model, $serial, $rel)
        }
    }
}

# ---------------------------------------------------------------- [4/4] 测试地址
Write-Step 4 '测试地址'
$lan = Get-LanIpv4 | Sort-Object -Property @{ Expression = {
            if ($_.IP -eq $androidHost) { 0 }
            elseif ($_.IP -like '192.168.*') { 1 }
            elseif ($_.IP -like '10.*') { 2 }
            else { 3 } } } | Select-Object -First 1
$lanIp = if ($lan) { $lan.IP } else { '<本机IPv4>' }
$lanAlias = if ($lan) { $lan.Alias } else { '' }
Write-Ok ("电脑局域网地址：{0}（网卡：{1}）" -f $lanIp, $lanAlias)
if ($androidHost) {
    if ($androidHost -eq $lanIp) {
        Write-Ok ("与 Android 配置一致：{0}" -f $androidUrl)
    } else {
        Write-Warn ("Android 当前配置为 {0}，与本机地址 {1} 不一致" -f $androidUrl, $lanIp)
        Write-Info '（如需更换：修改 android/gradle.properties 的 zhixue.webBaseUrl 后重新 Run；本脚本不修改配置）'
    }
}

# ---------------------------------------------------------------- 结果
$webText = if ($webOk) { '正常' } else { '异常' + $(if ($webNote) { '（' + $webNote + '）' } else { '' }) }
$androidText = if ($s24) { '已检测到 S24+' }
               elseif ($hasPhone) { '已检测到 Android 真机' }
               else { '未检测到真机（可用 Android Studio 手工运行）' }

Write-Host ''
Write-Host '================================' -ForegroundColor Cyan
Write-Host '英语 AI 学习系统测试环境' -ForegroundColor Cyan
Write-Host '================================' -ForegroundColor Cyan
Write-Host ("Web 服务：{0}" -f $webText)
Write-Host ("测试地址：http://{0}:{1}/" -f $lanIp, $Port)
Write-Host ("Android：{0}" -f $androidText)
Write-Host ("项目：{0}" -f $ProjectRoot)
Write-Host ''
if ($webOk) {
    Write-Host '现在可以打开 Android Studio，选择 S24+，点击 Run。' -ForegroundColor Green
} else {
    Write-Host 'Web 服务未就绪，请先不要进行手机验收。' -ForegroundColor Red
    Write-Host '（可在弹出的后端窗口中查看报错，或手工执行：python web\app.py --host 0.0.0.0）' -ForegroundColor DarkGray
}

if (-not $webOk) { exit 2 }
exit 0
