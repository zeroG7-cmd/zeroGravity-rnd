# Phase 2: Separate Operator state and capabilities from the Learning System
# Run from the root of zeroGravity-rnd after Phase 1 has been committed.
# This script moves only the Learning/Operator boundary and updates R&D Python paths.
# It does not touch Shadow, Lab databases, Zero Command, CAD, CV, sensors, or URDF.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Stop-WithMessage {
    param([string]$Message)
    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Ensure-Directory {
    param([string]$RelativePath)
    $fullPath = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}

function Remove-GitKeep {
    param([string]$RelativeDirectory)
    $gitKeep = Join-Path (Join-Path $RepoRoot $RelativeDirectory) ".gitkeep"
    if (Test-Path $gitKeep) {
        Remove-Item $gitKeep -Force
    }
}

function Move-TrackedItem {
    param(
        [string]$Source,
        [string]$Destination
    )

    $sourcePath = Join-Path $RepoRoot $Source
    $destinationPath = Join-Path $RepoRoot $Destination

    if (-not (Test-Path $sourcePath)) {
        Write-Host "SKIP: $Source was not found." -ForegroundColor Yellow
        return
    }

    if (Test-Path $destinationPath) {
        Stop-WithMessage "Destination already exists: $Destination"
    }

    $destinationParent = Split-Path $destinationPath -Parent
    if (-not (Test-Path $destinationParent)) {
        New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
    }

    git mv -- "$Source" "$Destination"
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "Git could not move '$Source' to '$Destination'."
    }

    Write-Host "MOVED: $Source -> $Destination" -ForegroundColor Green
}

function Replace-InFile {
    param(
        [string]$RelativePath,
        [hashtable]$Replacements
    )

    $fullPath = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path $fullPath)) {
        Stop-WithMessage "Required source file was not found: $RelativePath"
    }

    $content = Get-Content -Raw -Path $fullPath
    $updated = $content

    foreach ($oldText in $Replacements.Keys) {
        $updated = $updated.Replace($oldText, $Replacements[$oldText])
    }

    if ($updated -eq $content) {
        Write-Host "UNCHANGED: $RelativePath" -ForegroundColor Yellow
    }
    else {
        Set-Content -Path $fullPath -Value $updated -Encoding UTF8
        Write-Host "UPDATED: $RelativePath" -ForegroundColor Cyan
    }
}

$RepoRoot = (Get-Location).Path

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    Stop-WithMessage "Run this script from the root of the zeroGravity-rnd Git repository."
}

if (-not (Test-Path (Join-Path $RepoRoot "learning"))) {
    Stop-WithMessage "The learning directory was not found."
}

$currentBranch = git branch --show-current
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Git branch could not be determined."
}

if ($currentBranch -ne "migration/architecture-reconstruction") {
    Stop-WithMessage "You are on '$currentBranch'. Switch to 'migration/architecture-reconstruction' first."
}

$status = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Git status could not be read."
}

if ($status) {
    Write-Host ""
    Write-Host "Uncommitted changes were found:" -ForegroundColor Yellow
    git status --short
    Stop-WithMessage "Commit Phase 1 before running Phase 2."
}

Write-Host "Starting Phase 2 migration..." -ForegroundColor Cyan
Write-Host "Repository: $RepoRoot"
Write-Host ""

# Ensure agreed target directories exist.
$targetDirectories = @(
    "operator/capabilities",
    "operator/capabilities/backups",
    "operator/events",
    "operator/events/receipts",
    "operator/hubs/learning/history",
    "operator/hubs/learning/progress",
    "operator/hubs/learning/stats"
)

foreach ($directory in $targetDirectories) {
    Ensure-Directory $directory
    Remove-GitKeep $directory
}

# Operator learning state.
Move-TrackedItem "learning/operator/history.json" `
    "operator/hubs/learning/history/learning_history.json"

Move-TrackedItem "learning/operator/bootdev_history_imports.json" `
    "operator/hubs/learning/history/bootdev_history_imports.json"

Move-TrackedItem "learning/operator/stats.json" `
    "operator/hubs/learning/stats/learning_stats.json"

Move-TrackedItem "learning/operator/provider_events.json" `
    "operator/events/provider_events.json"

# Move each receipt individually so the target skeleton remains predictable.
$receiptsSource = Join-Path $RepoRoot "learning/operator/receipts"
if (Test-Path $receiptsSource) {
    Get-ChildItem -Path $receiptsSource -File | ForEach-Object {
        $relativeSource = "learning/operator/receipts/$($_.Name)"
        $relativeDestination = "operator/events/receipts/$($_.Name)"
        Move-TrackedItem $relativeSource $relativeDestination
    }

    if (-not (Get-ChildItem -Path $receiptsSource -Force)) {
        Remove-Item $receiptsSource -Force
    }
}

# Operator capability model.
Move-TrackedItem "learning/config/skill_tree.json" `
    "operator/capabilities/skill_tree.json"

Move-TrackedItem "learning/config/competencies.json" `
    "operator/capabilities/competencies.json"

Move-TrackedItem "learning/config/capability_graph.json" `
    "operator/capabilities/capability_graph.json"

Move-TrackedItem "learning/skill_tree.md" `
    "operator/capabilities/skill_tree.md"

$backupsSource = Join-Path $RepoRoot "learning/config/backups"
if (Test-Path $backupsSource) {
    Get-ChildItem -Path $backupsSource -File | ForEach-Object {
        $relativeSource = "learning/config/backups/$($_.Name)"
        $relativeDestination = "operator/capabilities/backups/$($_.Name)"
        Move-TrackedItem $relativeSource $relativeDestination
    }

    if (-not (Get-ChildItem -Path $backupsSource -Force)) {
        Remove-Item $backupsSource -Force
    }
}

# Remove the old learning/operator directory only when empty.
$oldOperatorDirectory = Join-Path $RepoRoot "learning/operator"
if ((Test-Path $oldOperatorDirectory) -and -not (Get-ChildItem $oldOperatorDirectory -Force)) {
    Remove-Item $oldOperatorDirectory -Force
}

Write-Host ""
Write-Host "Updating Learning Engine paths..." -ForegroundColor Cyan

Replace-InFile "learning/engine/stats.py" @{
    'SKILL_TREE_PATH = LEARNING_ROOT / "config" / "skill_tree.json"' =
        'SKILL_TREE_PATH = Path("operator/capabilities/skill_tree.json")'
    'COMPETENCIES_PATH = LEARNING_ROOT / "config" / "competencies.json"' =
        'COMPETENCIES_PATH = Path("operator/capabilities/competencies.json")'
    'OPERATOR_ROOT = LEARNING_ROOT / "operator"' =
        'OPERATOR_ROOT = Path("operator/hubs/learning")'
    'STATS_PATH = OPERATOR_ROOT / "stats.json"' =
        'STATS_PATH = OPERATOR_ROOT / "stats" / "learning_stats.json"'
}

Replace-InFile "learning/engine/history.py" @{
    'HISTORY_PATH = Path("learning/operator/history.json")' =
        'HISTORY_PATH = Path("operator/hubs/learning/history/learning_history.json")'
}

Replace-InFile "learning/engine/process_learning_event.py" @{
    "ROOT=Path('learning'); TRACKS=ROOT/'tracks'; LEDGER=ROOT/'operator'/'provider_events.json'; RECEIPTS=ROOT/'operator'/'receipts'" =
        "ROOT=Path('learning'); TRACKS=ROOT/'tracks'; LEDGER=Path('operator/events/provider_events.json'); RECEIPTS=Path('operator/events/receipts')"
}

Replace-InFile "learning/engine/concepts.py" @{
    'GRAPH_PATH = Path("learning/config/capability_graph.json")' =
        'GRAPH_PATH = Path("operator/capabilities/capability_graph.json")'
}

Replace-InFile "learning/engine/map_track_competencies.py" @{
    'COMPETENCIES_PATH = Path("learning/config/competencies.json")' =
        'COMPETENCIES_PATH = Path("operator/capabilities/competencies.json")'
}

Replace-InFile "learning/engine/reset_accidental_fusion_xp.py" @{
    'COMPETENCIES_PATH = Path("learning/config/competencies.json")' =
        'COMPETENCIES_PATH = Path("operator/capabilities/competencies.json")'
    'HISTORY_PATH = Path("learning/operator/history.json")' =
        'HISTORY_PATH = Path("operator/hubs/learning/history/learning_history.json")'
}

Replace-InFile "learning/engine/backfill_concepts.py" @{
    "LEDGER_PATH=Path('learning/operator/concept_backfill.json')" =
        "LEDGER_PATH=Path('operator/hubs/learning/progress/concept_backfill.json')"
}

Replace-InFile "learning/scripts/sync_skill_tree.py" @{
    'learning/config/skill_tree.json' =
        'operator/capabilities/skill_tree.json'
    'learning/config/competencies.json' =
        'operator/capabilities/competencies.json'
    'LEARNING_ROOT / "skill_tree.md"' =
        'PROJECT_ROOT / "operator" / "capabilities" / "skill_tree.md"'
    'LEARNING_ROOT / "config" / "skill_tree.json"' =
        'PROJECT_ROOT / "operator" / "capabilities" / "skill_tree.json"'
    'LEARNING_ROOT / "config" / "competencies.json"' =
        'PROJECT_ROOT / "operator" / "capabilities" / "competencies.json"'
}

Write-Host ""
Write-Host "Checking for stale source-code path references..." -ForegroundColor Cyan

$stalePatterns = @(
    "learning/operator",
    "learning/config/skill_tree.json",
    "learning/config/competencies.json",
    "learning/config/capability_graph.json",
    "learning/skill_tree.md"
)

$sourceFiles = Get-ChildItem `
    -Path (Join-Path $RepoRoot "learning") `
    -Recurse `
    -File `
    -Include *.py,*.ps1

$staleMatches = @()

foreach ($sourceFile in $sourceFiles) {
    $text = Get-Content -Raw -Path $sourceFile.FullName

    foreach ($pattern in $stalePatterns) {
        if ($text.Contains($pattern)) {
            $staleMatches += "$($sourceFile.FullName): $pattern"
        }
    }
}

if ($staleMatches.Count -gt 0) {
    Write-Host ""
    Write-Host "Stale references remain:" -ForegroundColor Yellow
    $staleMatches | ForEach-Object { Write-Host $_ }
    Stop-WithMessage "Phase 2 stopped before testing. Send the stale-reference list back for review."
}

Write-Host "No stale source-code references were found." -ForegroundColor Green

Write-Host ""
Write-Host "Running Python compilation..." -ForegroundColor Cyan

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $pythonCommand) {
    Stop-WithMessage "Python was not found in PATH."
}

if ($pythonCommand.Name -eq "py.exe" -or $pythonCommand.Name -eq "py") {
    py -3 -m compileall -q learning scripts
}
else {
    python -m compileall -q learning scripts
}

if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Python compilation failed. Do not commit yet."
}

Write-Host "Python compilation passed." -ForegroundColor Green

Write-Host ""
Write-Host "Rebuilding Operator learning statistics..." -ForegroundColor Cyan

if ($pythonCommand.Name -eq "py.exe" -or $pythonCommand.Name -eq "py") {
    py -3 learning/engine/stats.py
}
else {
    python learning/engine/stats.py
}

if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "The Operator stats engine failed. Do not commit yet."
}

$expectedStats = Join-Path $RepoRoot "operator/hubs/learning/stats/learning_stats.json"
if (-not (Test-Path $expectedStats)) {
    Stop-WithMessage "The stats engine ran but did not create the expected learning_stats.json file."
}

Write-Host ""
Write-Host "Phase 2 completed successfully." -ForegroundColor Green
Write-Host ""
git status --short
Write-Host ""
Write-Host "Review the changes, then commit with:"
Write-Host 'git add .'
Write-Host 'git commit -m "separate operator state from learning system"'
