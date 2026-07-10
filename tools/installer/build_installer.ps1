# Build the standalone QUA Libraries Installer on Windows.
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

foreach ($python in @("py", "python3", "python")) {
    if (Get-Command $python -ErrorAction SilentlyContinue) {
        if ($python -eq "py") {
            & $python -3.12 "$ScriptDir\build_installer.py" @args
        } else {
            & $python "$ScriptDir\build_installer.py" @args
        }
        exit $LASTEXITCODE
    }
}

Write-Error "Python 3 is required to build the installer."
exit 1
