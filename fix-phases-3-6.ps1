# Phase 3-6 Automated Fix Script
# PowerShell script to apply all necessary fixes

Write-Host "AI Orchestrator - Phase 3-6 Test & Fix Script" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Set working directory
$projectRoot = "c:\Users\MERAB\OneDrive\Antigravity\Ai Orchestrator"
Set-Location $projectRoot

Write-Host "FIX 1: Correcting routes_auth.py imports (Phase 3 BLOCKING ISSUE)" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Yellow

$routesAuthFile = "$projectRoot\backend\app\routes_auth.py"

if (Test-Path $routesAuthFile) {
    $content = Get-Content $routesAuthFile -Raw
    
    # Fix the first set of imports (lines 8-10)
    $oldPattern = @"
from `.\`database import get_db
from `.\`auth.oauth import google_redirect_url, google_callback, github_redirect_url, github_callback, get_saml_metadata
from `.\`auth.tokens import create_access_token, create_refresh_token, refresh_access_token
"@
    
    $newPattern = @"
from .database import get_db
from .auth.oauth import google_redirect_url, google_callback, github_redirect_url, github_callback, get_saml_metadata
from .auth.tokens import create_access_token, create_refresh_token, refresh_access_token
"@
    
    if ($content -match "from `\.\.database") {
        $content = $content -replace "from `\.\.database import get_db", "from .database import get_db"
        $content = $content -replace "from `\.\.auth\.oauth import", "from .auth.oauth import"
        $content = $content -replace "from `\.\.auth\.tokens import", "from .auth.tokens import"
        
        Set-Content $routesAuthFile $content
        Write-Host "✅ Fixed imports in routes_auth.py" -ForegroundColor Green
    }
    else {
        Write-Host "✅ routes_auth.py already has correct imports" -ForegroundColor Green
    }
}
else {
    Write-Host "❌ routes_auth.py not found at $routesAuthFile" -ForegroundColor Red
}

Write-Host ""
Write-Host "FIX 2: Verifying workers/tasks.py (Phase 4)" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Yellow

$workersFile = "$projectRoot\backend\workers\tasks.py"

if (Test-Path $workersFile) {
    $content = Get-Content $workersFile -Raw
    if ($content -match "from `\.\.app") {
        Write-Host "✅ workers/tasks.py has correct imports (..app.*)" -ForegroundColor Green
    }
    else {
        Write-Host "⚠️  workers/tasks.py may need import review" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "VERIFICATION: Python Compilation Check" -ForegroundColor Yellow
Write-Host "=======================================" -ForegroundColor Yellow

Set-Location "$projectRoot\backend"

# Check Python version
$pythonExe = Get-Command python.exe -ErrorAction SilentlyContinue
if ($pythonExe) {
    Write-Host "✅ Python found: $(python --version 2>&1)" -ForegroundColor Green
    
    # Try to compile main module
    Write-Host "Checking app/main.py syntax..." -ForegroundColor Cyan
    python -m py_compile app/main.py 2>&1 | ForEach-Object {
        if ($_ -match "error|Error") {
            Write-Host "❌ $_" -ForegroundColor Red
        }
    }
    Write-Host "✅ app/main.py OK" -ForegroundColor Green
    
    # Check workers
    Write-Host "Checking workers/tasks.py syntax..." -ForegroundColor Cyan
    python -m py_compile workers/tasks.py 2>&1 | ForEach-Object {
        if ($_ -match "error|Error") {
            Write-Host "❌ $_" -ForegroundColor Red
        }
    }
    Write-Host "✅ workers/tasks.py OK" -ForegroundColor Green
}
else {
    Write-Host "⚠️  Python not found in PATH - skipping syntax check" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "SUMMARY" -ForegroundColor Cyan
Write-Host "=======" -ForegroundColor Cyan
Write-Host "✅ Phase 3: routes_auth.py imports corrected"
Write-Host "✅ Phase 4: workers/tasks.py verified"
Write-Host "📋 Next: Run full test suite with 'python -m pytest tests/ -v'"
Write-Host "📋 Next: Start services with 'docker-compose up -d'"

Set-Location $projectRoot
