[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "status", "stop")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $ProjectRoot ".runtime"
$LogRoot = Join-Path $RuntimeRoot "logs"
$StatePath = Join-Path $RuntimeRoot "connecthub-dev.json"
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BackendRoot = Join-Path $ProjectRoot "backend"
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$VitePath = Join-Path $FrontendRoot "node_modules\vite\bin\vite.js"
$PostgresBin = "C:\Program Files\PostgreSQL\18\bin"

function Get-PortOwner([int]$Port) {
    Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
}

function Get-CommandLine([int]$ProcessId) {
    (Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue).CommandLine
}

function Test-OwnedProcess([int]$ProcessId, [ValidateSet("backend", "frontend")] [string]$Kind) {
    $commandLine = Get-CommandLine $ProcessId
    if (-not $commandLine -or $commandLine.IndexOf($ProjectRoot, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return $false
    }
    if ($Kind -eq "backend") {
        return $commandLine.IndexOf($PythonPath, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
            $commandLine.IndexOf("run.py", [StringComparison]::OrdinalIgnoreCase) -ge 0
    }
    return $commandLine.IndexOf("vite", [StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Read-State {
    if (-not (Test-Path -LiteralPath $StatePath)) { return $null }
    Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
}

function Test-Http([string]$Uri) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 5
        return $response.StatusCode -eq 200
    }
    catch { return $false }
}

function Wait-Healthy {
    $deadline = (Get-Date).AddSeconds(45)
    do {
        $backendLive = Test-Http "http://127.0.0.1:8000/health/live"
        $backendReady = Test-Http "http://127.0.0.1:8000/health/ready"
        $frontend = Test-Http "http://127.0.0.1:5173/"
        $proxyReady = Test-Http "http://127.0.0.1:5173/health/ready"
        if ($backendLive -and $backendReady -and $frontend -and $proxyReady) { return $true }
        Start-Sleep -Milliseconds 750
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Stop-Owned([int]$ProcessId, [string]$Kind) {
    if (-not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) { return }
    if (-not (Test-OwnedProcess $ProcessId $Kind)) {
        throw "Refusing to stop PID $ProcessId because it is not the recorded ConnectHub $Kind process."
    }
    Stop-Process -Id $ProcessId
    Wait-Process -Id $ProcessId -Timeout 10 -ErrorAction SilentlyContinue
}

if ($Action -eq "status") {
    $state = Read-State
    if ($null -eq $state) {
        Write-Output "ConnectHub runtime state: stopped (no project PID file)."
        exit 0
    }
    $backendOwned = Test-OwnedProcess ([int]$state.backend_pid) "backend"
    $frontendOwned = Test-OwnedProcess ([int]$state.frontend_pid) "frontend"
    Write-Output "Backend PID $($state.backend_pid): $(if ($backendOwned) {'running/owned'} else {'not running or identity mismatch'})"
    Write-Output "Frontend PID $($state.frontend_pid): $(if ($frontendOwned) {'running/owned'} else {'not running or identity mismatch'})"
    Write-Output "Backend live: $(Test-Http 'http://127.0.0.1:8000/health/live')"
    Write-Output "Backend ready: $(Test-Http 'http://127.0.0.1:8000/health/ready')"
    Write-Output "Frontend root: $(Test-Http 'http://127.0.0.1:5173/')"
    Write-Output "Frontend proxy ready: $(Test-Http 'http://127.0.0.1:5173/health/ready')"
    exit $(if ($backendOwned -and $frontendOwned) { 0 } else { 1 })
}

if ($Action -eq "stop") {
    $state = Read-State
    if ($null -eq $state) {
        Write-Output "No ConnectHub PID file exists; nothing was stopped."
        exit 0
    }
    Stop-Owned ([int]$state.frontend_pid) "frontend"
    Stop-Owned ([int]$state.backend_pid) "backend"
    Remove-Item -LiteralPath $StatePath -Force
    Write-Output "Stopped only the ConnectHub processes recorded in $StatePath."
    exit 0
}

if (Test-Path -LiteralPath $StatePath) {
    throw "A ConnectHub PID file already exists. Run status or stop before starting another pair."
}
foreach ($port in 8000, 5173) {
    $listener = Get-PortOwner $port
    if ($listener) {
        $commandLine = Get-CommandLine ([int]$listener.OwningProcess)
        throw "Port $port is already occupied by PID $($listener.OwningProcess). No process was stopped. Command: $commandLine"
    }
}
if (-not (Test-Path -LiteralPath $PythonPath)) { throw "Project interpreter not found: $PythonPath" }
if (-not (Test-Path -LiteralPath $VitePath)) { throw "Vite is not installed in frontend/node_modules. Run npm ci in frontend first." }
if (-not (Test-Path -LiteralPath (Join-Path $PostgresBin "libpq.dll"))) { throw "PostgreSQL 18 libpq was not found in $PostgresBin" }
$NodePath = (Get-Command node -ErrorAction Stop).Source

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backendOut = Join-Path $LogRoot "backend-$timestamp.out.log"
$backendErr = Join-Path $LogRoot "backend-$timestamp.err.log"
$frontendOut = Join-Path $LogRoot "frontend-$timestamp.out.log"
$frontendErr = Join-Path $LogRoot "frontend-$timestamp.err.log"

$oldImpl = $env:PSYCOPG_IMPL
$oldPath = $env:PATH
$oldCsrf = $env:CSRF_SECRET
$backendProcess = $null
$frontendProcess = $null
try {
    $env:PSYCOPG_IMPL = "python"
    $env:PATH = "$PostgresBin;$oldPath"
    $secretBytes = New-Object byte[] 48
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($secretBytes)
    }
    finally {
        $rng.Dispose()
    }
    $env:CSRF_SECRET = [BitConverter]::ToString($secretBytes).Replace("-", "")
    $backendProcess = Start-Process -FilePath $PythonPath -ArgumentList ".\run.py" -WorkingDirectory $BackendRoot -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru

    $viteArgument = '"{0}" --host 127.0.0.1 --port 5173 --strictPort' -f $VitePath
    $frontendProcess = Start-Process -FilePath $NodePath -ArgumentList $viteArgument -WorkingDirectory $FrontendRoot -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru
}
finally {
    $env:PSYCOPG_IMPL = $oldImpl
    $env:PATH = $oldPath
    $env:CSRF_SECRET = $oldCsrf
}

if (-not (Wait-Healthy)) {
    if ($frontendProcess) { Stop-Owned $frontendProcess.Id "frontend" }
    if ($backendProcess) { Stop-Owned $backendProcess.Id "backend" }
    throw "ConnectHub did not become healthy within 45 seconds. Inspect the project-local .runtime/logs files."
}

$state = [ordered]@{
    started_at = (Get-Date).ToString("o")
    backend_pid = $backendProcess.Id
    frontend_pid = $frontendProcess.Id
    backend_stdout = $backendOut
    backend_stderr = $backendErr
    frontend_stdout = $frontendOut
    frontend_stderr = $frontendErr
}
$state | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8
Write-Output "ConnectHub started on loopback. Backend PID $($backendProcess.Id); frontend PID $($frontendProcess.Id)."
Write-Output "Backend: http://127.0.0.1:8000  Frontend: http://127.0.0.1:5173"
