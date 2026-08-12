Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (Get-Command python -ErrorAction SilentlyContinue) {
    python launch.py
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 launch.py
} else {
    Write-Error "Python 3.10 or newer is required but was not found on your PATH."
}
