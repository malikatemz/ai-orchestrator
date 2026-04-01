param(
    [Parameter(Mandatory = $true)]
    [string]$ProductionBaseUrl,

    [Parameter(Mandatory = $false)]
    [string]$LocalBaseUrl = "http://localhost:8000"
)

$localRuntime = Invoke-RestMethod -Uri "$LocalBaseUrl/diagnostics/runtime"
$productionRuntime = Invoke-RestMethod -Uri "$ProductionBaseUrl/diagnostics/runtime"

Write-Host "Local runtime fingerprint:"
$localRuntime | ConvertTo-Json -Depth 6

Write-Host "`nProduction runtime fingerprint:"
$productionRuntime | ConvertTo-Json -Depth 6
