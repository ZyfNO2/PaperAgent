[CmdletBinding()]
param(
    [string]$ConfigPath = "config/provider-router-balanced.example.json",
    [int]$Requests = 24,
    [int]$Concurrency = 8,
    [int]$RequireSuccessfulEndpoints = 2,
    [string]$OutputPath = "artifacts/provider-router-load-report.json",
    [switch]$SkipInstall,
    [switch]$SkipSemantic,
    [switch]$SkipLive
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-PythonCommand {
    param([Parameter(Mandatory = $true)][string[]]$CommandArgs)
    & python @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "python command failed with exit code ${LASTEXITCODE}: python $($CommandArgs -join ' ')"
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if (-not $SkipInstall) {
        Write-Host "[1/3] Installing PaperAgent development dependencies..."
        Invoke-PythonCommand -CommandArgs @("-m", "pip", "install", "-e", ".[dev]")
    }

    if (-not $SkipSemantic) {
        Write-Host "[2/3] Running role-bound semantic and router regression tests..."
        Invoke-PythonCommand -CommandArgs @(
            "-m", "pytest", "-q",
            "tests/methodology/test_strict_method_design.py",
            "tests/methodology/test_method_design_draft.py",
            "tests/evals/test_academic_tailoring_retrieval_v1_scorer.py",
            "tests/evals/test_academic_tailoring_retrieval_v2_scorer.py",
            "tests/providers/test_routing_llm_provider.py",
            "tests/scripts/test_provider_router_load.py"
        )
    }

    if (-not $SkipLive) {
        Write-Host "[3/3] Running live concurrent router probes..."
        Invoke-PythonCommand -CommandArgs @(
            "scripts/test_provider_router_load.py",
            "--config", $ConfigPath,
            "--requests", "$Requests",
            "--concurrency", "$Concurrency",
            "--output", $OutputPath
        )

        $report = Get-Content -Raw -Encoding UTF8 $OutputPath | ConvertFrom-Json
        $successfulEndpoints = @(
            $report.endpoints.PSObject.Properties |
                Where-Object { [int]$_.Value.successes -gt 0 }
        )
        if ($report.status -ne "passed") {
            throw "router load report status is '$($report.status)', expected 'passed'"
        }
        if ($successfulEndpoints.Count -lt $RequireSuccessfulEndpoints) {
            $distribution = @(
                $report.endpoints.PSObject.Properties |
                    ForEach-Object { "$($_.Name)=$([int]$_.Value.successes)" }
            ) -join ", "
            throw "only $($successfulEndpoints.Count) endpoints completed requests; required ${RequireSuccessfulEndpoints}. Distribution: $distribution"
        }

        Write-Host "Router validation passed."
        Write-Host "  Throughput: $($report.throughput_requests_per_second) requests/s"
        Write-Host "  Request p95: $($report.request_latency_ms.p95) ms"
        Write-Host "  Successful endpoints: $($successfulEndpoints.Count)"
        foreach ($entry in $report.endpoints.PSObject.Properties) {
            Write-Host "  - $($entry.Name): calls=$($entry.Value.calls), successes=$($entry.Value.successes), failures=$($entry.Value.failures), p95=$($entry.Value.latency_ms.p95) ms"
        }
        Write-Host "  Report: $((Resolve-Path $OutputPath).Path)"
    }
}
finally {
    Pop-Location
}
