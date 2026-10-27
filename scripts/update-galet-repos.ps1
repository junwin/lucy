[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$ReposRoot = $PSScriptRoot,

    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Command $($Arguments -join ' ')"
    }
}

if (-not (Get-Command $PythonCommand -ErrorAction SilentlyContinue)) {
    if ($PythonCommand -eq "python" -and (Get-Command "py" -ErrorAction SilentlyContinue)) {
        $PythonCommand = "py"
    }
    else {
        throw "Python command not found: $PythonCommand"
    }
}

$ReposRoot = [System.IO.Path]::GetFullPath($ReposRoot)
$Repos = @(
    "galet",
    "galet-tools",
    "galet-memory",
    "galet-prompt-builder"
)

Write-Host "Repository root: $ReposRoot"
Write-Host "Update order: $($Repos -join ' -> ')"

foreach ($RepoName in $Repos) {
    $RepoDir = Join-Path $ReposRoot $RepoName
    $GitDir = Join-Path $RepoDir ".git"
    $VenvDir = Join-Path $RepoDir ".venv"
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"

    if (-not (Test-Path -LiteralPath $GitDir -PathType Container)) {
        throw "Git repository not found: $RepoDir"
    }

    Write-Host ""
    Write-Host "===== $RepoName ====="

    Invoke-Checked -Command "git" -Arguments @("-C", $RepoDir, "switch", "main")
    Invoke-Checked -Command "git" -Arguments @("-C", $RepoDir, "pull", "--ff-only", "origin", "main")

    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        Invoke-Checked -Command $PythonCommand -Arguments @("-m", "venv", $VenvDir)
    }

    Invoke-Checked -Command $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")

    if ($RepoName -in @("galet-memory", "galet-prompt-builder")) {
        Invoke-Checked -Command $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "${RepoDir}[test]")
    }
    else {
        Invoke-Checked -Command $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", $RepoDir, "pytest")
    }

    Push-Location $RepoDir
    try {
        Invoke-Checked -Command $VenvPython -Arguments @("-m", "pytest")
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "All Galet repositories updated and tested successfully."
