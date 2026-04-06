# Comprehensive Phase Testing Script (PowerShell)
# Tests Phases 3, 4, 5, 6 systematically

param(
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Continue"
$ProjectRoot = "c:\Users\MERAB\OneDrive\Antigravity\Ai Orchestrator"
$BackendDir = "$ProjectRoot\backend"
$FrontendDir = "$ProjectRoot\frontend"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "AI ORCHESTRATOR - PHASE TEST SUITE" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Track results
$results = @()

function Test-Phase {
    param(
        [string]$Phase,
        [string]$TestName,
        [scriptblock]$TestBlock
    )
    
    try {
        $result = @($TestBlock.Invoke())
        if ($result[0]) {
            Write-Host ("✅ " + $Phase + " - " + $TestName) -ForegroundColor Green
            $results += @{Phase=$Phase; Test=$TestName; Status="PASS"}
            return $true
        } else {
            Write-Host ("❌ " + $Phase + " - " + $TestName) -ForegroundColor Red
            $results += @{Phase=$Phase; Test=$TestName; Status="FAIL"}
            return $false
        }
    } catch {
        $errorMsg = $PSItem.Exception.Message
        Write-Host ("❌ " + $Phase + " - " + $TestName + " : " + $errorMsg) -ForegroundColor Red
        $results += @{Phase=$Phase; Test=$TestName; Status="ERROR"}
        return $false
    }
}

# ============ PHASE 3: Stripe Billing Integration ============

Write-Host "PHASE 3: Stripe Billing Integration" -ForegroundColor Yellow
Write-Host "====================================" -ForegroundColor Yellow
Write-Host ""

Test-Phase "Phase 3" "routes_auth.py imports fixed" {
    $content = Get-Content "$BackendDir\app\routes_auth.py"
    $hasCorrectImport = $content | Select-String -Pattern "from \.database import get_db" -Quiet
    return $hasCorrectImport
}

Test-Phase "Phase 3" "routes_billing.py imports correct" {
    $content = Get-Content "$BackendDir\app\routes_billing.py"
    $hasCorrectImport = $content | Select-String -Pattern "from \.billing import" -Quiet
    return $hasCorrectImport
}

Test-Phase "Phase 3" "Billing module files exist" {
    return (Test-Path "$BackendDir\app\billing\__init__.py") -and `
           (Test-Path "$BackendDir\app\billing\service.py") -and `
           (Test-Path "$BackendDir\app\billing\models.py")
}

Test-Phase "Phase 3" "Billing test file exists" {
    return Test-Path "$BackendDir\tests\test_billing.py"
}

Test-Phase "Phase 3" "Stripe configuration in config.py" {
    $content = Get-Content "$BackendDir\app\config.py"
    $hasStripeConfig = $content | Select-String -Pattern "stripe" -Quiet
    return $hasStripeConfig
}

# ============ PHASE 4: Celery Worker Integration ============

Write-Host ""
Write-Host "PHASE 4: Celery Worker Integration" -ForegroundColor Yellow
Write-Host "===================================" -ForegroundColor Yellow
Write-Host ""

Test-Phase "Phase 4" "workers/tasks.py has correct imports" {
    $content = Get-Content "$BackendDir\workers\tasks.py"
    $hasCorrectImport = $content | Select-String -Pattern "from \.\.\app\." -Quiet
    return $hasCorrectImport
}

Test-Phase "Phase 4" "Celery tasks defined" {
    $content = Get-Content "$BackendDir\workers\tasks.py"
    $hasTasks = $content | Select-String -Pattern "@shared_task" -Quiet
    return $hasTasks
}

Test-Phase "Phase 4" "Worker test file exists" {
    return Test-Path "$BackendDir\tests\test_worker.py"
}

Test-Phase "Phase 4" "requirements.txt has Celery" {
    $content = Get-Content "$BackendDir\requirements.txt"
    $hasCelery = $content | Select-String -Pattern "celery" -Quiet
    return $hasCelery
}

Test-Phase "Phase 4" "workers/__init__.py exists" {
    return Test-Path "$BackendDir\workers\__init__.py"
}

# ============ PHASE 5: Frontend Auth Integration ============

Write-Host ""
Write-Host "PHASE 5: Frontend Auth Integration" -ForegroundColor Yellow
Write-Host "===================================" -ForegroundColor Yellow
Write-Host ""

Test-Phase "Phase 5" "Frontend directory exists" {
    return Test-Path "$FrontendDir"
}

Test-Phase "Phase 5" "Next.js package.json exists" {
    return Test-Path "$FrontendDir\package.json"
}

Test-Phase "Phase 5" "TypeScript config exists" {
    return Test-Path "$FrontendDir\tsconfig.json"
}

Test-Phase "Phase 5" "Auth test file exists" {
    return Test-Path "$BackendDir\tests\test_auth.py"
}

Test-Phase "Phase 5" "OAuth modules configured" {
    $content = Get-Content "$BackendDir\app\auth\oauth.py"
    $hasOAuth = $content | Select-String -Pattern "google|github" -Quiet
    return $hasOAuth
}

# ============ PHASE 6: Documentation & Deployment ============

Write-Host ""
Write-Host "PHASE 6: Documentation & Deployment" -ForegroundColor Yellow
Write-Host "====================================" -ForegroundColor Yellow
Write-Host ""

$docFiles = @(
    "START_HERE.md",
    "README.md",
    "GETTING_STARTED.md",
    "DEPLOYMENT_READY.md",
    "PROJECT_SUMMARY.txt"
)

foreach ($doc in $docFiles) {
    Test-Phase "Phase 6" ("Documentation: " + $doc) {
        return Test-Path "$ProjectRoot\$doc"
    }
}

Test-Phase "Phase 6" "Docker Compose configured" {
    return (Test-Path "$ProjectRoot\docker-compose.yml") -and `
           (Test-Path "$ProjectRoot\Dockerfile")
}

Test-Phase "Phase 6" "Kubernetes manifests exist" {
    $k8sDir = "$ProjectRoot\k8s"
    return (Test-Path $k8sDir) -and (Get-ChildItem $k8sDir -Filter "*.yaml" | Measure-Object).Count -gt 0
}

Test-Phase "Phase 6" "GitHub Actions CI/CD configured" {
    $workflowDir = "$ProjectRoot\.github\workflows"
    return (Test-Path $workflowDir) -and (Get-ChildItem $workflowDir -Filter "*.yml" | Measure-Object).Count -gt 0
}

# ============ SUMMARY ============

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "TEST SUMMARY" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$phase3Pass = ($results | Where-Object {$_.Phase -eq "Phase 3" -and $_.Status -eq "PASS"} | Measure-Object).Count
$phase3Total = ($results | Where-Object {$_.Phase -eq "Phase 3"} | Measure-Object).Count

$phase4Pass = ($results | Where-Object {$_.Phase -eq "Phase 4" -and $_.Status -eq "PASS"} | Measure-Object).Count
$phase4Total = ($results | Where-Object {$_.Phase -eq "Phase 4"} | Measure-Object).Count

$phase5Pass = ($results | Where-Object {$_.Phase -eq "Phase 5" -and $_.Status -eq "PASS"} | Measure-Object).Count
$phase5Total = ($results | Where-Object {$_.Phase -eq "Phase 5"} | Measure-Object).Count

$phase6Pass = ($results | Where-Object {$_.Phase -eq "Phase 6" -and $_.Status -eq "PASS"} | Measure-Object).Count
$phase6Total = ($results | Where-Object {$_.Phase -eq "Phase 6"} | Measure-Object).Count

Write-Host ""
Write-Host ("Phase 3 (Billing):       " + $phase3Pass + " / " + $phase3Total + " passed") -ForegroundColor $(if ($phase3Pass -eq $phase3Total) { 'Green' } else { 'Yellow' })
Write-Host ("Phase 4 (Workers):       " + $phase4Pass + " / " + $phase4Total + " passed") -ForegroundColor $(if ($phase4Pass -eq $phase4Total) { 'Green' } else { 'Yellow' })
Write-Host ("Phase 5 (Frontend Auth): " + $phase5Pass + " / " + $phase5Total + " passed") -ForegroundColor $(if ($phase5Pass -eq $phase5Total) { 'Green' } else { 'Yellow' })
Write-Host ("Phase 6 (Deployment):    " + $phase6Pass + " / " + $phase6Total + " passed") -ForegroundColor $(if ($phase6Pass -eq $phase6Total) { 'Green' } else { 'Yellow' })

$totalPass = $results | Where-Object {$_.Status -eq "PASS"} | Measure-Object
$totalTests = $results.Count

Write-Host ""
Write-Host ("TOTAL: " + $totalPass.Count + " / " + $totalTests + " tests passed") -ForegroundColor $(if ($totalPass.Count -eq $totalTests) { 'Green' } else { 'Yellow' })

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1 - Configure Python environment:"
Write-Host "   python -m venv venv"
Write-Host "   .\venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "2 - Install dependencies:"
Write-Host "   cd backend"
Write-Host "   pip install -r requirements.txt"
Write-Host ""
Write-Host "3 - Run backend tests:"
Write-Host "   python -m pytest tests/ -v"
Write-Host ""
Write-Host "4 - Install frontend dependencies:"
Write-Host "   cd ../frontend"
Write-Host "   npm install"
Write-Host ""
Write-Host "5 - Start all services:"
Write-Host "   cd .."
Write-Host "   docker-compose up -d"
Write-Host ""
