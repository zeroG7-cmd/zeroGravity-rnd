# Phase 1: Prepare zeroGravity-rnd for incremental migration
# This script creates a Git branch and the new directory skeleton.
# It does NOT move, rename, or delete existing project files.

[CmdletBinding()]
param(
    [string]$BranchName = "migration/architecture-reconstruction"
)

$ErrorActionPreference = "Stop"

function Stop-WithMessage {
    param([string]$Message)
    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

$RepoRoot = (Get-Location).Path

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    Stop-WithMessage "Run this script from the root of your zeroGravity-rnd Git repository."
}

$RequiredItems = @(
    "learning",
    "database",
    "scripts"
)

foreach ($item in $RequiredItems) {
    if (-not (Test-Path (Join-Path $RepoRoot $item))) {
        Stop-WithMessage "Expected '$item' was not found. Confirm that this is the original zeroGravity-rnd repository."
    }
}

Write-Host "Repository: $RepoRoot" -ForegroundColor Cyan

$status = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Git status could not be read."
}

if ($status) {
    Write-Host ""
    Write-Host "Your repository has uncommitted changes:" -ForegroundColor Yellow
    git status --short
    Stop-WithMessage "Commit or stash these changes before beginning the migration."
}

$currentBranch = git branch --show-current
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "The current Git branch could not be determined."
}

Write-Host "Current branch: $currentBranch"

$branchExists = git branch --list $BranchName
if ($branchExists) {
    Write-Host "Migration branch already exists. Switching to it..." -ForegroundColor Yellow
    git switch $BranchName
}
else {
    Write-Host "Creating migration branch: $BranchName" -ForegroundColor Green
    git switch -c $BranchName
}

if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Git could not create or switch to the migration branch."
}

$Directories = @(
    "operator",
    "operator/profile",
    "operator/capabilities",
    "operator/evidence",
    "operator/events",
    "operator/integrations",
    "operator/summaries/daily",
    "operator/summaries/weekly",
    "operator/summaries/monthly",
    "operator/summaries/annual",

    "operator/hubs/learning/history",
    "operator/hubs/learning/progress",
    "operator/hubs/learning/stats",

    "operator/hubs/nutrition/history",
    "operator/hubs/nutrition/progress",
    "operator/hubs/nutrition/stats",

    "operator/hubs/fitness/history",
    "operator/hubs/fitness/progress",
    "operator/hubs/fitness/stats",

    "operator/hubs/health/history",
    "operator/hubs/health/progress",
    "operator/hubs/health/stats",

    "operator/hubs/martial_arts/history",
    "operator/hubs/martial_arts/progress",
    "operator/hubs/martial_arts/stats",

    "operator/hubs/spirit/history",
    "operator/hubs/spirit/progress",
    "operator/hubs/spirit/stats",

    "operator/hubs/projects/history",
    "operator/hubs/projects/progress",
    "operator/hubs/projects/stats",

    "journal/entries",
    "journal/templates",
    "journal/engine",
    "journal/config",
    "journal/indexes",
    "journal/extracted",
    "journal/integrations",
    "journal/summaries",
    "journal/logs",
    "journal/archive",

    "zero_world/overview",
    "zero_world/spirit",
    "zero_world/lore",
    "zero_world/characters",
    "zero_world/world",
    "zero_world/culture",
    "zero_world/technology",
    "zero_world/factions",
    "zero_world/stories",
    "zero_world/design_language",
    "zero_world/research",
    "zero_world/concepts",
    "zero_world/production",
    "zero_world/tracking",
    "zero_world/archive",

    "lab/research",
    "lab/experiments",
    "lab/prototypes",
    "lab/datasets",
    "lab/notebooks",
    "lab/reports",
    "lab/engine",
    "lab/database",
    "lab/archive",

    "projects/shadow/architecture",
    "projects/shadow/hardware",
    "projects/shadow/cad",
    "projects/shadow/ros",
    "projects/shadow/simulation",
    "projects/shadow/perception",
    "projects/shadow/navigation",
    "projects/shadow/control",
    "projects/shadow/sensors",
    "projects/shadow/telemetry",
    "projects/shadow/tests",
    "projects/shadow/data",
    "projects/shadow/deployments",
    "projects/shadow/docs",

    "shared/libraries",
    "shared/schemas",
    "shared/config",
    "shared/utilities"
)

foreach ($relativePath in $Directories) {
    $fullPath = Join-Path $RepoRoot $relativePath

    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }

    $gitKeep = Join-Path $fullPath ".gitkeep"
    if (-not (Test-Path $gitKeep)) {
        New-Item -ItemType File -Path $gitKeep -Force | Out-Null
    }
}

Write-Host ""
Write-Host "Running baseline Python compilation check..." -ForegroundColor Cyan

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
}

if ($pythonCommand) {
    if ($pythonCommand.Name -eq "py.exe" -or $pythonCommand.Name -eq "py") {
        py -3 -m compileall -q learning scripts
    }
    else {
        python -m compileall -q learning scripts
    }

    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "The existing Python code did not pass the baseline compilation check. No existing files were moved, but inspect the errors before continuing."
    }

    Write-Host "Baseline Python compilation passed." -ForegroundColor Green
}
else {
    Write-Host "Python was not found in PATH. Skeleton creation completed, but compilation was skipped." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Phase 1 preparation completed." -ForegroundColor Green
Write-Host "No existing project files were moved or deleted."
Write-Host ""
git status --short
Write-Host ""
Write-Host "Review the new skeleton, then commit it with:"
Write-Host 'git add .'
Write-Host 'git commit -m "prepare architecture migration skeleton"'
