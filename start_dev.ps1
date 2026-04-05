# ProxyPoolMaster Development Startup Script
# Usage: Right-click -> "Run with PowerShell" or: powershell -ExecutionPolicy Bypass -File start_dev.ps1

param(
    [switch]$Backend,
    [switch]$API,
    [switch]$Frontend,
    [switch]$All
)

# If no parameter specified, start all
if (-not ($Backend -or $API -or $Frontend)) {
    $All = $true
}

# Set console encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$projectRoot = Get-Location

# ===========================================
# Load environment variables from .env file
# ===========================================
function Load-EnvFile {
    param([string]$EnvFilePath)
    
    if (Test-Path $EnvFilePath) {
        Write-Host "[INFO] Loading environment from: $EnvFilePath" -ForegroundColor Gray
        Get-Content $EnvFilePath | ForEach-Object {
            # Skip empty lines and comments
            if ($_ -match '^\s*#' -or $_ -match '^\s*$') {
                return
            }
            # Parse KEY=VALUE format
            if ($_ -match '^\s*([^=]+)\s*=\s*(.*?)\s*$') {
                $key = $matches[1]
                $value = $matches[2]
                # Remove quotes if present
                if ($value -match '^["''](.*)["'']$') {
                    $value = $matches[1]
                }
                # Only set if not already set (allow command line override)
                if (-not [Environment]::GetEnvironmentVariable($key)) {
                    [Environment]::SetEnvironmentVariable($key, $value, 'Process')
                }
            }
        }
    } else {
        Write-Host "[WARNING] .env file not found at: $EnvFilePath" -ForegroundColor Yellow
        Write-Host "          Using default values..." -ForegroundColor Yellow
    }
}

# Load .env file
$envFile = Join-Path $projectRoot ".env"
Load-EnvFile -EnvFilePath $envFile

# ===========================================
# Set default values if not loaded from .env
# ===========================================

# Essential defaults (used if not in .env)
if (-not $env:REDIS_HOST) { $env:REDIS_HOST = "localhost" }
if (-not $env:REDIS_PORT) { $env:REDIS_PORT = "6379" }
if (-not $env:REDIS_DB) { $env:REDIS_DB = "0" }
if (-not $env:API_TOKEN) { $env:API_TOKEN = "test" }
if (-not $env:LOG_LEVEL) { $env:LOG_LEVEL = "INFO" }
if (-not $env:PYTHONIOENCODING) { $env:PYTHONIOENCODING = "utf-8" }

# Port configuration
$API_PORT = 8000
$FRONTEND_PORT = 5173

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ProxyPoolMaster - Development Mode" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ===========================================
# Check and install dependencies
# ===========================================
Write-Host "[Check] Checking Python dependencies..." -ForegroundColor Yellow

# Check concurrent-log-handler
$concurrentLogHandlerCheck = pip show concurrent-log-handler 2>&1
if (-not $concurrentLogHandlerCheck -or $concurrentLogHandlerCheck -match "not found") {
    Write-Host "  Installing concurrent-log-handler..." -ForegroundColor Yellow
    pip install concurrent-log-handler>=0.9.20
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] concurrent-log-handler installed" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Failed to install concurrent-log-handler" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [OK] concurrent-log-handler is installed" -ForegroundColor Green
}

# ===========================================
# Ensure logs directory exists
# ===========================================
$logsDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    Write-Host "[OK] Created logs directory: $logsDir" -ForegroundColor Green
} else {
    Write-Host "[OK] Logs directory exists: $logsDir" -ForegroundColor Green
}

# ===========================================
# Create .gitkeep for logs directory
# ===========================================
$gitkeepFile = Join-Path $logsDir ".gitkeep"
if (-not (Test-Path $gitkeepFile)) {
    "# Keep logs directory in git" | Out-File -FilePath $gitkeepFile -Encoding UTF8
}

# Function to check and free port
function Test-AndFreePort {
    param($Port, $ServiceName)
    
    Write-Host "[Check] Checking port $Port for $ServiceName..." -ForegroundColor Yellow
    $connection = netstat -ano | Select-String ":$Port"
    if ($connection) {
        Write-Host "  Port $Port is occupied, attempting to free..." -ForegroundColor Yellow
        $line = $connection[0].ToString()
        $parts = $line -split '\s+'
        $processId = $parts[-1]
        try {
            taskkill /PID $processId /F 2>$null
            Write-Host "  OK: Freed port $Port (killed PID $processId)" -ForegroundColor Green
            Start-Sleep -Seconds 2
        } catch {
            Write-Host "  WARNING: Could not free port $Port" -ForegroundColor Red
            return $false
        }
    } else {
        Write-Host "  OK: Port $Port is available" -ForegroundColor Green
    }
    return $true
}

# Check ports
if ($All -or $API) {
    $apiPortOk = Test-AndFreePort -Port $API_PORT -ServiceName "API"
    if (-not $apiPortOk) {
        Write-Host "[ERROR] Cannot use port $API_PORT" -ForegroundColor Red
        exit 1
    }
}

# Check Redis
if ($All -or $Backend -or $API) {
    $redisHost = $env:REDIS_HOST
    $redisPort = $env:REDIS_PORT
    Write-Host "[Check] Checking Redis connection to $redisHost`:$redisPort..." -ForegroundColor Yellow
    try {
        $redisTest = python -c "import redis; r=redis.Redis(host='$redisHost',port=$redisPort); print('OK' if r.ping() else 'FAIL')" 2>&1
        if ($redisTest -contains "OK") {
            Write-Host "  [OK] Redis is running on $redisHost`:$redisPort" -ForegroundColor Green
        } else {
            Write-Host "  [ERROR] Redis connection failed!" -ForegroundColor Red
            Write-Host "         Start Redis: docker run -d --name redis-dev -p 6379:6379 redis:7-alpine" -ForegroundColor Yellow
            exit 1
        }
    } catch {
        Write-Host "  [ERROR] Redis check failed: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""

# Start Backend (Collectors + Testers)
if ($All -or $Backend) {
    Write-Host "[1/3] Starting Backend (Collectors + Testers)..." -ForegroundColor Yellow
    $backendCmd = @"
Set-Location '$projectRoot'

# Load .env file function
function Load-EnvFile {
    param([string]`$EnvFilePath)
    if (Test-Path `$EnvFilePath) {
        Get-Content `$EnvFilePath | ForEach-Object {
            if (`$_ -match '^\s*#' -or `$_ -match '^\s*$') { return }
            if (`$_ -match '^\s*([^=]+)\s*=\s*(.*?)\s*$') {
                `$key = `$matches[1]
                `$value = `$matches[2]
                if (`$value -match '^["''](.*)["'']$') { `$value = `$matches[1] }
                [Environment]::SetEnvironmentVariable(`$key, `$value, 'Process')
            }
        }
    }
}

# Load environment
Load-EnvFile -EnvFilePath '$envFile'

# Set defaults if not in .env
if (-not `$env:REDIS_HOST) { `$env:REDIS_HOST = 'localhost' }
if (-not `$env:API_TOKEN) { `$env:API_TOKEN = 'test' }
if (-not `$env:LOG_LEVEL) { `$env:LOG_LEVEL = 'INFO' }
if (-not `$env:PYTHONIOENCODING) { `$env:PYTHONIOENCODING = 'utf-8' }

Write-Host '[Backend] Starting...' -ForegroundColor Cyan
python main.py
Write-Host '`n[Backend Stopped]' -ForegroundColor Red
pause
"@
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
    Start-Sleep -Seconds 2
}

# Start API Server
if ($All -or $API) {
    Write-Host "[2/3] Starting API Server on port $API_PORT..." -ForegroundColor Yellow
    
    # 如果同时启动 Backend，设置标记让 API 不启动 Collector / Tester（避免重复）
    $disableTester = if ($All -or $Backend) { "1" } else { "0" }
    $disableCollector = if ($All -or $Backend) { "1" } else { "0" }
    
    $apiCmd = @"
Set-Location '$projectRoot'

# Load .env file function
function Load-EnvFile {
    param([string]`$EnvFilePath)
    if (Test-Path `$EnvFilePath) {
        Get-Content `$EnvFilePath | ForEach-Object {
            if (`$_ -match '^\s*#' -or `$_ -match '^\s*$') { return }
            if (`$_ -match '^\s*([^=]+)\s*=\s*(.*?)\s*$') {
                `$key = `$matches[1]
                `$value = `$matches[2]
                if (`$value -match '^["''](.*)["'']$') { `$value = `$matches[1] }
                [Environment]::SetEnvironmentVariable(`$key, `$value, 'Process')
            }
        }
    }
}

# Load environment
Load-EnvFile -EnvFilePath '$envFile'

# Set defaults if not in .env
if (-not `$env:REDIS_HOST) { `$env:REDIS_HOST = 'localhost' }
if (-not `$env:API_TOKEN) { `$env:API_TOKEN = 'test' }
if (-not `$env:LOG_LEVEL) { `$env:LOG_LEVEL = 'INFO' }
if (-not `$env:PYTHONIOENCODING) { `$env:PYTHONIOENCODING = 'utf-8' }

# 如果 Backend 已启动，禁用 API 中的 Collector / Tester 避免重复
if ("$disableCollector" -eq "1") {
    `$env:DISABLE_API_COLLECTOR = "1"
}

if ("$disableTester" -eq "1") {
    `$env:DISABLE_API_TESTER = "1"
    Write-Host '[API] Starting on port $API_PORT (Collector/Tester disabled, using Backend scheduler)...' -ForegroundColor Cyan
} else {
    Write-Host '[API] Starting on port $API_PORT (with Tester)...' -ForegroundColor Cyan
}

# Use python src/api/main.py to enable custom logging configuration
# Add --reload flag for development auto-reload
python src/api/main.py --reload
Write-Host '`n[API Server Stopped]' -ForegroundColor Red
pause
"@
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $apiCmd -WindowStyle Normal
    Start-Sleep -Seconds 2
}

# Start Frontend
if ($All -or $Frontend) {
    Write-Host "[3/3] Starting Frontend..." -ForegroundColor Yellow
    $frontendCmd = @"
Set-Location '$projectRoot\web-ui'
if (-not (Test-Path 'node_modules')) {
    Write-Host '[Frontend] Installing dependencies...' -ForegroundColor Yellow
    npm install
}
Write-Host '[Frontend] Starting dev server...' -ForegroundColor Cyan
npm run dev
Write-Host '`n[Frontend Stopped]' -ForegroundColor Red
pause
"@
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  All services started successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Cyan
Write-Host "  Frontend:  http://localhost:$FRONTEND_PORT" -ForegroundColor Yellow
Write-Host "  API Docs:  http://localhost:$API_PORT/docs" -ForegroundColor Yellow
Write-Host "  Health:    http://localhost:$API_PORT/health" -ForegroundColor Yellow
Write-Host "  Logs:      .\logs\app.log (unified)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Log Components:" -ForegroundColor Cyan
Write-Host "  [APP]       - Main application" -ForegroundColor Gray
Write-Host "  [API]       - API server requests" -ForegroundColor Gray
Write-Host "  [COLLECTOR] - Proxy collectors" -ForegroundColor Gray
Write-Host "  [TESTER]    - Proxy testers" -ForegroundColor Gray
Write-Host "  [REDIS]     - Redis operations" -ForegroundColor Gray
Write-Host ""
Write-Host "Press any key to close this window..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
