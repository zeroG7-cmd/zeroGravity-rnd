# Phase 3A: Audit and classify the existing R&D repository
# This script is READ-ONLY with respect to existing R&D content.
# It creates reports under reports/migration/ but does not move or delete project files.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Stop-WithMessage {
    param([string]$Message)
    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

$RepoRoot = (Get-Location).Path

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    Stop-WithMessage "Run this script from the root of zeroGravity-rnd."
}

$currentBranch = git branch --show-current
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Git branch could not be determined."
}

if ($currentBranch -ne "migration/architecture-reconstruction") {
    Stop-WithMessage "You are on '$currentBranch'. Switch to 'migration/architecture-reconstruction'."
}

$status = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Git status could not be read."
}

if ($status) {
    Write-Host ""
    Write-Host "Uncommitted changes were found:" -ForegroundColor Yellow
    git status --short
    Stop-WithMessage "Commit the completed Learning/Operator migration before auditing Shadow."
}

$AuditRoots = @(
    "ai",
    "cad",
    "cv",
    "sensors",
    "urdf",
    "experiments",
    "experiments_archive",
    "data",
    "database",
    "docs"
)

$ReportRoot = Join-Path $RepoRoot "reports/migration"
New-Item -ItemType Directory -Path $ReportRoot -Force | Out-Null

$InventoryCsv = Join-Path $ReportRoot "phase_03_shadow_inventory.csv"
$InventoryJson = Join-Path $ReportRoot "phase_03_shadow_inventory.json"
$ReferenceReport = Join-Path $ReportRoot "phase_03_path_references.txt"
$SummaryReport = Join-Path $ReportRoot "phase_03_shadow_audit_summary.md"

function Get-RelativePath {
    param([string]$FullPath)

    return [System.IO.Path]::GetRelativePath($RepoRoot, $FullPath).Replace("\", "/")
}

function Get-Classification {
    param([string]$RelativePath)

    $path = $RelativePath.ToLowerInvariant()

    # Explicit long-term R&D records.
    if ($path.StartsWith("experiments_archive/")) {
        return @{
            Destination = "lab/archive/experiments"
            Confidence = "high"
            Reason = "Archived experiments are Lab records rather than project runtime assets."
        }
    }

    if ($path.StartsWith("experiments/")) {
        return @{
            Destination = "lab/experiments"
            Confidence = "high"
            Reason = "Experiments belong to the reusable Lab workflow."
        }
    }

    # Project geometry and simulation model.
    if ($path.StartsWith("cad/")) {
        return @{
            Destination = "projects/shadow/cad"
            Confidence = "high"
            Reason = "Existing CAD content appears to describe Shadow hardware and assemblies."
        }
    }

    if ($path.StartsWith("urdf/")) {
        return @{
            Destination = "projects/shadow/simulation/urdf"
            Confidence = "high"
            Reason = "URDF is the Shadow robot simulation model."
        }
    }

    # Sensors are primarily Shadow hardware, but generic studies may need review.
    if ($path.StartsWith("sensors/")) {
        if ($path -match "test|lidar|camera|imu|navio|gps|range|sensor") {
            return @{
                Destination = "projects/shadow/hardware/sensors"
                Confidence = "medium"
                Reason = "Sensor material is likely tied to Shadow hardware testing."
            }
        }

        return @{
            Destination = "REVIEW:sensors"
            Confidence = "low"
            Reason = "Could be project hardware or reusable sensor research."
        }
    }

    # Computer vision implementation versus reusable learning/research.
    if ($path.StartsWith("cv/")) {
        if ($path -match "pipeline|stream|camera|tracking|detect|perception|opencv|video") {
            return @{
                Destination = "projects/shadow/perception/computer_vision"
                Confidence = "medium"
                Reason = "Likely implementation or prototype for Shadow perception."
            }
        }

        return @{
            Destination = "REVIEW:cv"
            Confidence = "low"
            Reason = "Could be Shadow perception, a Lab experiment, or general learning material."
        }
    }

    # AI is intentionally conservative.
    if ($path.StartsWith("ai/")) {
        if ($path -match "navigation|perception|tracking|control|mission|agent|drone|shadow") {
            return @{
                Destination = "projects/shadow/intelligence"
                Confidence = "medium"
                Reason = "AI appears directly associated with Shadow autonomy."
            }
        }

        if ($path -match "model|dataset|training|notebook|research|prototype|experiment") {
            return @{
                Destination = "lab/research/ai"
                Confidence = "medium"
                Reason = "Reusable AI research and training assets belong in Lab."
            }
        }

        return @{
            Destination = "REVIEW:ai"
            Confidence = "low"
            Reason = "AI content needs semantic classification before moving."
        }
    }

    # Data must be split by purpose.
    if ($path.StartsWith("data/")) {
        if ($path -match "simulation|hardware|telemetry|camera|bags|logs|missions") {
            return @{
                Destination = "projects/shadow/data"
                Confidence = "medium"
                Reason = "Likely Shadow simulation, hardware, telemetry, camera, or mission data."
            }
        }

        if ($path -match "dataset|training|research|experiment") {
            return @{
                Destination = "lab/datasets"
                Confidence = "medium"
                Reason = "Reusable research datasets belong to Lab."
            }
        }

        return @{
            Destination = "REVIEW:data"
            Confidence = "low"
            Reason = "Data must be separated by ownership and lifecycle."
        }
    }

    # Preserve database identity initially.
    if ($path -eq "database/shadow.db") {
        return @{
            Destination = "projects/shadow/data/runtime/shadow.db"
            Confidence = "high"
            Reason = "Shadow runtime/test database."
        }
    }

    if ($path -eq "database/zerogravity_rnd.db") {
        return @{
            Destination = "lab/database/zerogravity_rnd.db"
            Confidence = "high"
            Reason = "Long-term R&D and experiment database."
        }
    }

    if ($path.StartsWith("database/")) {
        return @{
            Destination = "REVIEW:database"
            Confidence = "low"
            Reason = "Database identity must be confirmed before migration."
        }
    }

    # Documentation can be project-specific or platform-wide.
    if ($path.StartsWith("docs/")) {
        if ($path -match "shadow|drone|simulation|perception|navigation|hardware|sensor|camera|lidar|ros") {
            return @{
                Destination = "projects/shadow/docs"
                Confidence = "medium"
                Reason = "Documentation appears Shadow-specific."
            }
        }

        if ($path -match "experiment|research|pipeline|workflow|lab") {
            return @{
                Destination = "lab/reports"
                Confidence = "medium"
                Reason = "Documentation appears to describe R&D methods or experiment workflows."
            }
        }

        return @{
            Destination = "REVIEW:docs"
            Confidence = "low"
            Reason = "Could be project, Lab, or repository-level documentation."
        }
    }

    return @{
        Destination = "REVIEW:unknown"
        Confidence = "low"
        Reason = "No classification rule matched."
    }
}

$records = New-Object System.Collections.Generic.List[object]

foreach ($root in $AuditRoots) {
    $rootPath = Join-Path $RepoRoot $root

    if (-not (Test-Path $rootPath)) {
        Write-Host "SKIP: $root does not exist." -ForegroundColor Yellow
        continue
    }

    Get-ChildItem -Path $rootPath -Recurse -File -Force | ForEach-Object {
        $relativePath = Get-RelativePath $_.FullName
        $classification = Get-Classification $relativePath

        $records.Add([PSCustomObject]@{
            source_path = $relativePath
            source_root = $root
            extension = $_.Extension.ToLowerInvariant()
            size_bytes = $_.Length
            proposed_destination = $classification.Destination
            confidence = $classification.Confidence
            reason = $classification.Reason
        })
    }
}

$records |
    Sort-Object source_path |
    Export-Csv -Path $InventoryCsv -NoTypeInformation -Encoding UTF8

$records |
    Sort-Object source_path |
    ConvertTo-Json -Depth 4 |
    Set-Content -Path $InventoryJson -Encoding UTF8

# Search source/config/docs files for old top-level path references.
$SearchExtensions = @(
    ".py", ".ps1", ".md", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".txt", ".html", ".js", ".css",
    ".xml", ".urdf", ".xacro", ".launch"
)

$ExcludedPrefixes = @(
    ".git/",
    "learning/resources/",
    "reports/migration/"
)

$ReferencePatterns = @(
    "ai/",
    "cad/",
    "cv/",
    "sensors/",
    "urdf/",
    "experiments/",
    "experiments_archive/",
    "data/",
    "database/",
    "docs/"
)

$referenceLines = New-Object System.Collections.Generic.List[string]

Get-ChildItem -Path $RepoRoot -Recurse -File -Force |
    Where-Object {
        $relative = Get-RelativePath $_.FullName
        $extensionAllowed = $SearchExtensions -contains $_.Extension.ToLowerInvariant()
        $excluded = $false

        foreach ($prefix in $ExcludedPrefixes) {
            if ($relative.StartsWith($prefix)) {
                $excluded = $true
                break
            }
        }

        $extensionAllowed -and -not $excluded
    } |
    ForEach-Object {
        $relative = Get-RelativePath $_.FullName
        $text = Get-Content -Raw -Path $_.FullName -ErrorAction SilentlyContinue

        if ($null -eq $text) {
            $text = ""
        }

        foreach ($pattern in $ReferencePatterns) {
            if ($text.Contains($pattern)) {
                $referenceLines.Add("$relative`t$pattern")
            }
        }
    }

$referenceLines |
    Sort-Object -Unique |
    Set-Content -Path $ReferenceReport -Encoding UTF8

$totalFiles = $records.Count
$totalBytes = ($records | Measure-Object -Property size_bytes -Sum).Sum
if ($null -eq $totalBytes) { $totalBytes = 0 }

$destinationGroups = $records |
    Group-Object proposed_destination |
    Sort-Object Count -Descending

$confidenceGroups = $records |
    Group-Object confidence |
    Sort-Object Name

$summary = New-Object System.Collections.Generic.List[string]
$summary.Add("# Phase 3 Shadow and Lab Audit")
$summary.Add("")
$summary.Add("This report was generated without moving or deleting existing R&D content.")
$summary.Add("")
$summary.Add("## Inventory")
$summary.Add("")
$summary.Add("- Files audited: $totalFiles")
$summary.Add("- Total bytes audited: $totalBytes")
$summary.Add("- Current branch: $currentBranch")
$summary.Add("")
$summary.Add("## Proposed destinations")
$summary.Add("")

foreach ($group in $destinationGroups) {
    $summary.Add("- ``$($group.Name)``: $($group.Count) files")
}

$summary.Add("")
$summary.Add("## Confidence")
$summary.Add("")

foreach ($group in $confidenceGroups) {
    $summary.Add("- $($group.Name): $($group.Count) files")
}

$summary.Add("")
$summary.Add("## Generated reports")
$summary.Add("")
$summary.Add("- ``reports/migration/phase_03_shadow_inventory.csv``")
$summary.Add("- ``reports/migration/phase_03_shadow_inventory.json``")
$summary.Add("- ``reports/migration/phase_03_path_references.txt``")
$summary.Add("")
$summary.Add("## Migration rule")
$summary.Add("")
$summary.Add("Only high-confidence groups should be moved automatically. Medium-confidence groups should be reviewed by folder. Low-confidence and ``REVIEW:*`` entries must be classified before any move.")

$summary |
    Set-Content -Path $SummaryReport -Encoding UTF8

Write-Host ""
Write-Host "Phase 3A audit completed." -ForegroundColor Green
Write-Host "No existing R&D files were moved or deleted."
Write-Host ""
Write-Host "Files audited: $totalFiles"
Write-Host "Inventory CSV: $InventoryCsv"
Write-Host "Inventory JSON: $InventoryJson"
Write-Host "Path references: $ReferenceReport"
Write-Host "Summary: $SummaryReport"
Write-Host ""
Write-Host "Proposed destination totals:" -ForegroundColor Cyan

$destinationGroups | ForEach-Object {
    Write-Host ("  {0,-55} {1,6}" -f $_.Name, $_.Count)
}

Write-Host ""
Write-Host "Review entries:" -ForegroundColor Yellow
$records |
    Where-Object { $_.proposed_destination.StartsWith("REVIEW:") } |
    Group-Object proposed_destination |
    Sort-Object Name |
    ForEach-Object {
        Write-Host ("  {0,-55} {1,6}" -f $_.Name, $_.Count)
    }

Write-Host ""
git status --short
