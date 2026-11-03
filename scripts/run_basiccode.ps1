[CmdletBinding()]
param(
    [ValidateSet('Check', 'Smoke', 'Run', 'Resume', 'Status', 'Plot')]
    [string]$Stage = 'Check',
    [string]$RunId,
    [string]$ResultDirectory,
    [string]$Python,
    [ValidateSet('isolated','concurrent')][string]$Mode = 'isolated',
    [int]$Workers = 2
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $venvPython = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
    $Python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }
}
if ($Stage -in @('Smoke', 'Run','Status','Resume') -and -not $RunId) {
    throw 'Supply a unique -RunId. Existing result folders are never overwritten.'
}
if ($Stage -eq 'Plot' -and -not $ResultDirectory) {
    throw 'Supply -ResultDirectory pointing to a completed saved run.'
}

Push-Location -LiteralPath $repositoryRoot
try {
    switch ($Stage) {
        'Check' {
            & $Python --version
            if ($LASTEXITCODE -ne 0) { throw 'Python could not start.' }
            & $Python -m unittest tests.test_basiccode_unknown_mask tests.test_basiccode_benchmark tests.test_basiccode_retry -v
        }
        'Smoke' { & $Python -m benchmarks.basiccode_runner --smoke --run-id $RunId }
        'Run' { & $Python -m benchmarks.basiccode_runner --run-id $RunId --mode $Mode --workers $Workers }
        'Resume' { & $Python -m benchmarks.basiccode_runner --run-id $RunId --mode $Mode --workers $Workers --resume }
        'Status' { & $Python -m benchmarks.basiccode_runner --run-id $RunId --status }
        'Plot' { & $Python -m benchmarks.basiccode_plot $ResultDirectory }
    }
    if ($LASTEXITCODE -ne 0) { throw "basiccode $Stage failed with exit code $LASTEXITCODE. Retain the result folder." }
} finally {
    Pop-Location
}
