# Test script to verify development environment setup
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ProxyPoolMaster - Environment Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allPassed = $true

# Test 1: Python
Write-Host "[Test 1/6] Checking Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Python not found" -ForegroundColor Red
    $allPassed = $false
}

# Test 2: Node.js
Write-Host "[Test 2/6] Checking Node.js..." -ForegroundColor Yellow
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: Node.js $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Node.js not found" -ForegroundColor Red
    $allPassed = $false
}

# Test 3: Redis
Write-Host "[Test 3/6] Checking Redis..." -ForegroundColor Yellow
try {
    $redis = Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue
    if ($redis.TcpTestSucceeded) {
        Write-Host "  OK: Redis is running on localhost:6379" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: Redis not responding on port 6379" -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host "  FAIL: Could not test Redis connection" -ForegroundColor Red
    $allPassed = $false
}

# Test 4: Python Dependencies
Write-Host "[Test 4/6] Checking Python dependencies..." -ForegroundColor Yellow
$deps = @("fastapi", "uvicorn", "redis", "slowapi", "websockets")
$depsOk = $true
foreach ($dep in $deps) {
    $result = python -c "import $dep" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: $dep" -ForegroundColor Green
    } else {
        Write-Host "  FAIL: $dep not installed" -ForegroundColor Red
        $depsOk = $false
        $allPassed = $false
    }
}

# Test 5: Frontend Dependencies
Write-Host "[Test 5/6] Checking Frontend dependencies..." -ForegroundColor Yellow
if (Test-Path "web-ui\node_modules") {
    Write-Host "  OK: node_modules exists" -ForegroundColor Green
} else {
    Write-Host "  WARN: node_modules not found, will install on first run" -ForegroundColor Yellow
}

# Test 6: API Import Test
Write-Host "[Test 6/6] Checking API module import..." -ForegroundColor Yellow
$env:REDIS_HOST = "localhost"
$env:API_TOKEN = "test"
$importTest = python -c "from src.api.main import app; print('OK')" 2>&1
if ($importTest -contains "OK") {
    Write-Host "  OK: API module imports successfully" -ForegroundColor Green
} else {
    Write-Host "  FAIL: API module import failed" -ForegroundColor Red
    $allPassed = $false
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($allPassed) {
    Write-Host "  All tests PASSED! " -ForegroundColor Green
    Write-Host "  Run 'start_dev.ps1' to start development server" -ForegroundColor Cyan
} else {
    Write-Host "  Some tests FAILED" -ForegroundColor Red
    Write-Host "  Please fix the issues above" -ForegroundColor Yellow
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
pause
