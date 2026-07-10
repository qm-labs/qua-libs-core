# QUA Libraries installer launcher (Windows PowerShell).
# Opens the GUI by default; pass arguments for the CLI installer.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallPy = Join-Path $ScriptDir "install.py"
$InstallGui = Join-Path $ScriptDir "install_gui.py"

foreach ($python in @("python3", "python", "py")) {
    if (Get-Command $python -ErrorAction SilentlyContinue) {
        if ($args.Count -eq 0) {
            & $python $InstallGui
        } else {
            & $python $InstallPy @args
        }
        exit $LASTEXITCODE
    }
}

Write-Error "Python 3 is required to run the installer."
exit 1
