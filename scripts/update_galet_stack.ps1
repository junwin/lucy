param(
    [string]$ReposRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Update the local Galet-family repositories and reinstall them editable into
# Lucy's virtual environment in dependency order.
#
# Expected sibling layout by default:
#   <repos>\lucy
#   <repos>\galet
#   <repos>\galet-memory
#   <repos>\galet-tools
#   <repos>\galet-prompt-builder
#
# Usage:
#   .\scripts\update_galet_stack.ps1
#   .\scripts\update_galet_stack.ps1 -ReposRoot C:\Users\junwi\src\repos

$LucyRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $ReposRoot) {
    $ReposRoot = Split-Path $LucyRoot -Parent
}
$ReposRoot = (Resolve-Path $ReposRoot).Path

$VenvCandidates = @(
    (Join-Path $LucyRoot ".venv\Scripts\python.exe"),
    (Join-Path $LucyRoot "venv\Scripts\python.exe")
)
$Python = $VenvCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Python) {
    throw "Lucy virtual environment not found (.venv or venv)."
}

$Repos = @(
    "galet",
    "galet-memory",
    "galet-tools",
    "galet-prompt-builder"
)

function Invoke-Git {
    param(
        [string]$RepoPath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$GitArgs
    )

    & git -C $RepoPath @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git failed in $RepoPath: git $($GitArgs -join ' ')"
    }
}

function Test-RepoClean {
    param([string]$Repo)

    $Path = Join-Path $ReposRoot $Repo
    if (-not (Test-Path (Join-Path $Path ".git"))) {
        throw "Repository not found: $Path"
    }

    $Status = & git -C $Path status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "git status failed in $Path"
    }
    if ($Status) {
        Write-Host "ERROR: $Repo has uncommitted/untracked changes; refusing to switch/pull."
        & git -C $Path status --short
        throw "$Repo worktree is not clean"
    }
}

function Update-Repo {
    param([string]$Repo)

    $Path = Join-Path $ReposRoot $Repo
    Write-Host ""
    Write-Host "=== Updating $Repo ==="
    Invoke-Git $Path fetch origin main
    Invoke-Git $Path checkout main
    Invoke-Git $Path pull --ff-only origin main
    $Sha = (& git -C $Path rev-parse --short HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not determine HEAD for $Repo"
    }
    Write-Host "$Repo -> $Sha"
}

function Install-Repo {
    param([string]$Repo)

    $Path = Join-Path $ReposRoot $Repo
    Write-Host ""
    Write-Host "=== Installing $Repo editable ==="
    & $Python -m pip install --no-deps -e $Path
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed for $Repo"
    }
}

Write-Host "Lucy root : $LucyRoot"
Write-Host "Repos root: $ReposRoot"
Write-Host "Python    : $Python"
& $Python --version
if ($LASTEXITCODE -ne 0) {
    throw "Python check failed"
}

foreach ($Repo in $Repos) {
    Test-RepoClean $Repo
}

# Dependency order matters:
#   galet -> galet-memory -> galet-tools -> galet-prompt-builder
foreach ($Repo in $Repos) {
    Update-Repo $Repo
    Install-Repo $Repo
}

Write-Host ""
Write-Host "=== Verifying imports ==="
$Verify = @'
import galet
import galet_memory
import galet_tools
import galet_prompt_builder

for module in (galet, galet_memory, galet_tools, galet_prompt_builder):
    print(f"{module.__name__:22} {module.__file__}")
'@
$Verify | & $Python -
if ($LASTEXITCODE -ne 0) {
    throw "Import verification failed"
}

Write-Host ""
Write-Host "=== pip check ==="
& $Python -m pip check
if ($LASTEXITCODE -ne 0) {
    throw "pip check failed"
}

Write-Host ""
Write-Host "Galet stack update complete."
