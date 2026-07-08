# QUA Libraries installer launcher (Windows PowerShell).
# Runs install.py; later steps will bootstrap uv + Python here.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallPy = Join-Path $ScriptDir "install.py"

foreach ($python in @("python3", "python", "py")) {
    if (Get-Command $python -ErrorAction SilentlyContinue) {
        & $python $InstallPy @args
        exit $LASTEXITCODE
    }
}

Write-Error "Python 3 is required to run the installer."
exit 1
