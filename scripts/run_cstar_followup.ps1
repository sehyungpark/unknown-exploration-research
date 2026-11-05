[CmdletBinding()]
param(
    [ValidateSet('Check', 'Prepare', 'Test', 'Timing', 'Memory', 'Status', 'All')]
    [string]$Stage = 'Check',
    [string]$RunId,
    [string]$PythonExe
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPrefix = @()

if (-not $PythonExe) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        $PythonExe = $launcher.Source
        $pythonPrefix = @('-3')
    } else {
        $interpreter = Get-Command python -ErrorAction SilentlyContinue
        if (-not $interpreter) { throw 'Install Python 3.12+ or pass -PythonExe with its executable path.' }
        $PythonExe = $interpreter.Source
    }
}

if ($Stage -ne 'Check' -and -not $RunId) {
    throw '-RunId is required for Prepare, Test, Timing, Memory, Status, and All.'
}

$arguments = $pythonPrefix + @('-u', '-m', 'research.cstar_followup_runner', $Stage.ToLowerInvariant())
if ($RunId) { $arguments += @('--run-id', $RunId) }

Push-Location -LiteralPath $repoRoot
try {
    & $PythonExe @arguments
    $runExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($runExitCode -ne 0) { throw "C* follow-up failed (exit $runExitCode). Retain the run directory and its logs." }
