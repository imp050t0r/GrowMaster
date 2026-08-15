param(
    [switch]$SelfTest,
    [string]$ProtocolUri
)

$ErrorActionPreference = "Stop"
$stateRoot = Join-Path $env:APPDATA "GrowMaster"
$envFile = Join-Path $stateRoot ".env"
$composeFile = Join-Path (Join-Path $PSScriptRoot "app") "docker-compose.yml"
$logFile = Join-Path $stateRoot "storage-migration.log"
$script:DockerExecutable = $null

function Write-MigrationLog([string]$Message) {
    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    "$(Get-Date -Format o) $Message" | Add-Content -LiteralPath $logFile -Encoding UTF8
}

function Show-GrowMasterMessage(
    [string]$Message,
    [string]$Title = "GrowMaster",
    [System.Windows.MessageBoxButton]$Buttons = [System.Windows.MessageBoxButton]::OK,
    [System.Windows.MessageBoxImage]$Icon = [System.Windows.MessageBoxImage]::Information
) {
    Add-Type -AssemblyName PresentationFramework
    return [System.Windows.MessageBox]::Show($Message, $Title, $Buttons, $Icon)
}

function Find-DockerExecutable {
    $command = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Docker\Docker\resources\bin\docker.exe")
    )
    return $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

function Read-GrowMasterEnvironment([string]$Path) {
    $values = @{}
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $key = $Matches[1]
            $value = $Matches[2].Trim()
            if ($value.Length -ge 2 -and $value[0] -eq '"' -and $value[$value.Length - 1] -eq '"') {
                $value = $value.Substring(1, $value.Length - 2)
            }
            $values[$key] = $value.Replace('$$', '$').Replace('\"', '"')
        }
    }
    return $values
}

function Format-EnvironmentPath([string]$Path) {
    $value = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $value = $value.Replace('\', '/').Replace('$', '$$').Replace('"', '\"')
    return '"' + $value + '"'
}

function Set-GrowMasterEnvironmentValues(
    [string]$Path,
    [hashtable]$Values,
    [string]$BackupPath
) {
    $result = New-Object System.Collections.Generic.List[string]
    $seen = @{}
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=') {
            $key = $Matches[1]
            if ($Values.ContainsKey($key)) {
                if (-not $seen.ContainsKey($key)) {
                    $result.Add("$key=$($Values[$key])")
                    $seen[$key] = $true
                }
                continue
            }
        }
        $result.Add($line)
    }
    foreach ($key in $Values.Keys) {
        if (-not $seen.ContainsKey($key)) {
            $result.Add("$key=$($Values[$key])")
        }
    }

    $temporaryPath = "$Path.tmp-$([Guid]::NewGuid().ToString('N'))"
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllLines($temporaryPath, $result.ToArray(), $encoding)
    try {
        [IO.File]::Replace($temporaryPath, $Path, $BackupPath, $true)
    } catch {
        Copy-Item -LiteralPath $Path -Destination $BackupPath -Force
        Move-Item -LiteralPath $temporaryPath -Destination $Path -Force
    }
}

function Get-DirectorySummary([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return [PSCustomObject]@{ Files = 0; Bytes = [int64]0 }
    }
    $files = @(Get-ChildItem -LiteralPath $Path -File -Recurse -Force)
    $bytes = [int64]0
    foreach ($file in $files) { $bytes += $file.Length }
    return [PSCustomObject]@{ Files = $files.Count; Bytes = $bytes }
}

function Copy-DirectoryVerified([string]$Source, [string]$Destination) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    if (Test-Path -LiteralPath $Source) {
        Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
        }
    }
    $sourceSummary = Get-DirectorySummary $Source
    $destinationSummary = Get-DirectorySummary $Destination
    if (
        $sourceSummary.Files -ne $destinationSummary.Files -or
        $sourceSummary.Bytes -ne $destinationSummary.Bytes
    ) {
        throw "Kopiranih podatkov ni bilo mogoče preveriti. Stara baza je ostala nespremenjena."
    }
}

function Invoke-Docker([string[]]$Arguments, [string]$FailureMessage) {
    & $script:DockerExecutable @Arguments | Out-File -LiteralPath $logFile -Append -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw $FailureMessage }
}

function Test-ApplicationHealth {
    $deadline = (Get-Date).AddMinutes(3)
    do {
        try {
            $health = Invoke-RestMethod -Uri "http://localhost:3000/api/health" -TimeoutSec 4
            if ($health.status -eq "running") { return $true }
        } catch {
            Start-Sleep -Seconds 2
        }
    } until ((Get-Date) -gt $deadline)
    return $false
}

function Get-SelectedDataRoot([string]$CurrentRoot) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "Izberi novo mapo za GrowMasterjevo bazo in varnostne kopije."
    $dialog.ShowNewFolderButton = $true
    if (-not [string]::IsNullOrWhiteSpace($CurrentRoot) -and (Test-Path -LiteralPath $CurrentRoot)) {
        $dialog.SelectedPath = $CurrentRoot
    }
    try {
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { return $null }
        return [IO.Path]::GetFullPath($dialog.SelectedPath).TrimEnd('\', '/')
    } finally {
        $dialog.Dispose()
    }
}

function Test-RelatedPath([string]$First, [string]$Second) {
    $firstPath = [IO.Path]::GetFullPath($First).TrimEnd('\', '/')
    $secondPath = [IO.Path]::GetFullPath($Second).TrimEnd('\', '/')
    if ([string]::Equals($firstPath, $secondPath, [StringComparison]::OrdinalIgnoreCase)) { return $true }
    return (
        $firstPath.StartsWith($secondPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
        $secondPath.StartsWith($firstPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
    )
}

function Invoke-SelfTest {
    $testRoot = Join-Path ([IO.Path]::GetTempPath()) "GrowMasterMigrationSelfTest-$([Guid]::NewGuid().ToString('N'))"
    try {
        $sourceDatabase = Join-Path $testRoot "source\database"
        $sourceBackups = Join-Path $testRoot "source\backups"
        $copiedDatabase = Join-Path $testRoot "copied\database"
        New-Item -ItemType Directory -Path (Join-Path $sourceDatabase "base\1") -Force | Out-Null
        New-Item -ItemType Directory -Path $sourceBackups -Force | Out-Null
        [IO.File]::WriteAllText((Join-Path $sourceDatabase "PG_VERSION"), "16")
        [IO.File]::WriteAllBytes((Join-Path $sourceDatabase "base\1\123"), (1..64))
        [IO.File]::WriteAllText((Join-Path $sourceBackups "daily.json"), '{"ok":true}')
        Copy-DirectoryVerified $sourceDatabase $copiedDatabase

        $testEnvironment = Join-Path $testRoot ".env"
        $testEnvironmentBackup = Join-Path $testRoot ".env.before"
        [IO.File]::WriteAllLines(
            $testEnvironment,
            @('POSTGRES_DB=growmaster', 'POSTGRES_DATA_SOURCE="old/database"'),
            (New-Object System.Text.UTF8Encoding($false))
        )
        Set-GrowMasterEnvironmentValues $testEnvironment @{
            POSTGRES_DATA_SOURCE = (Format-EnvironmentPath $copiedDatabase)
            BACKUP_DATA_SOURCE = (Format-EnvironmentPath $sourceBackups)
            GROWMASTER_DATA_ROOT = (Format-EnvironmentPath (Join-Path $testRoot "copied"))
            GROWMASTER_WINDOWS_INSTALL = "true"
        } $testEnvironmentBackup
        $values = Read-GrowMasterEnvironment $testEnvironment
        if ($values["POSTGRES_DATA_SOURCE"] -ne [IO.Path]::GetFullPath($copiedDatabase).Replace('\', '/')) {
            throw "Self-test did not preserve the database path."
        }
        if ($values["GROWMASTER_WINDOWS_INSTALL"] -ne "true" -or -not (Test-Path -LiteralPath $testEnvironmentBackup)) {
            throw "Self-test did not update and back up the environment file."
        }
        Write-Output "GrowMaster storage migration self-test passed."
    } finally {
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\', '/')
        $resolvedTestRoot = [IO.Path]::GetFullPath($testRoot)
        if (
            $resolvedTestRoot.StartsWith($tempRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and
            (Split-Path -Leaf $resolvedTestRoot).StartsWith("GrowMasterMigrationSelfTest-")
        ) {
            Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-DataMigration {
    $mutex = New-Object System.Threading.Mutex($false, "Local\GrowMasterDataMigration")
    $hasMutex = $false
    $environmentBackup = $null
    $environmentUpdated = $false
    $composeBase = $null
    try {
        $hasMutex = $mutex.WaitOne(0)
        if (-not $hasMutex) {
            Show-GrowMasterMessage "Selitev podatkov je že odprta." "GrowMaster" | Out-Null
            return
        }
        if (-not (Test-Path -LiteralPath $envFile) -or -not (Test-Path -LiteralPath $composeFile)) {
            throw "Namestitev GrowMasterja ni popolna. Ponovno zaženi namestitveno datoteko."
        }
        $script:DockerExecutable = Find-DockerExecutable
        if (-not $script:DockerExecutable) { throw "Docker Desktop ni nameščen ali ni dosegljiv." }
        if (-not (& $script:DockerExecutable info 2>$null)) {
            throw "Najprej zaženi Docker Desktop in nato poskusi znova."
        }

        $environment = Read-GrowMasterEnvironment $envFile
        $databaseSource = $environment["POSTGRES_DATA_SOURCE"]
        $backupSource = $environment["BACKUP_DATA_SOURCE"]
        $databaseIsDirectory = -not [string]::IsNullOrWhiteSpace($databaseSource) -and [IO.Path]::IsPathRooted($databaseSource)
        $backupIsDirectory = -not [string]::IsNullOrWhiteSpace($backupSource) -and [IO.Path]::IsPathRooted($backupSource)
        $currentRoot = $environment["GROWMASTER_DATA_ROOT"]
        if (
            [string]::IsNullOrWhiteSpace($currentRoot) -and
            $databaseIsDirectory -and
            $backupIsDirectory
        ) {
            $databaseParent = [IO.Path]::GetFullPath((Split-Path -Parent $databaseSource)).TrimEnd('\', '/')
            $backupParent = [IO.Path]::GetFullPath((Split-Path -Parent $backupSource)).TrimEnd('\', '/')
            if ([string]::Equals($databaseParent, $backupParent, [StringComparison]::OrdinalIgnoreCase)) {
                $currentRoot = $databaseParent
            }
        }

        $targetRoot = Get-SelectedDataRoot $currentRoot
        if ([string]::IsNullOrWhiteSpace($targetRoot)) { return }
        if ($targetRoot.StartsWith('\\')) {
            throw "Izberi mapo na lokalnem disku. Omrežna mapa ni primerna za podatkovno bazo."
        }
        if (-not [string]::IsNullOrWhiteSpace($currentRoot) -and (Test-RelatedPath $targetRoot $currentRoot)) {
            throw "Izberi drugo, ločeno mapo. Nova mapa ne sme biti ista kot trenutna mapa ali ležati znotraj nje."
        }
        if (
            ($databaseIsDirectory -and (Test-RelatedPath $targetRoot $databaseSource)) -or
            ($backupIsDirectory -and (Test-RelatedPath $targetRoot $backupSource))
        ) {
            throw "Nova mapa mora biti ločena od trenutne baze in varnostnih kopij."
        }
        $databaseDestination = Join-Path $targetRoot "database"
        $backupDestination = Join-Path $targetRoot "backups"
        if ((Test-Path -LiteralPath $databaseDestination) -or (Test-Path -LiteralPath $backupDestination)) {
            throw "V izbrani mapi že obstaja mapa database ali backups. Zaradi varnosti izberi novo oziroma prazno mapo."
        }

        if ($databaseIsDirectory -and $backupIsDirectory) {
            $databaseSummary = Get-DirectorySummary $databaseSource
            $backupSummary = Get-DirectorySummary $backupSource
            try {
                $drive = New-Object IO.DriveInfo([IO.Path]::GetPathRoot($targetRoot))
                $requiredBytes = $databaseSummary.Bytes + $backupSummary.Bytes + 104857600
                if ($drive.AvailableFreeSpace -lt $requiredBytes) {
                    throw "Na izbranem disku ni dovolj prostora za varno kopijo podatkov."
                }
            } catch [System.ArgumentException] {
                # UNC and some removable locations cannot report free space here; copying still verifies every file.
            }
        }

        $confirmation = Show-GrowMasterMessage (
            "GrowMaster bo za nekaj minut ustavil aplikacijo in kopiral podatke v:`n`n$targetRoot`n`n" +
            "Stara kopija bo ostala nedotaknjena. Želiš nadaljevati?"
        ) "Prestavi GrowMasterjeve podatke" ([System.Windows.MessageBoxButton]::YesNo) ([System.Windows.MessageBoxImage]::Warning)
        if ($confirmation -ne [System.Windows.MessageBoxResult]::Yes) { return }

        New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
        $stagingRoot = Join-Path $targetRoot ".growmaster-migration-$([Guid]::NewGuid().ToString('N'))"
        $stagingDatabase = Join-Path $stagingRoot "database"
        $stagingBackups = Join-Path $stagingRoot "backups"
        New-Item -ItemType Directory -Path $stagingDatabase -Force | Out-Null
        New-Item -ItemType Directory -Path $stagingBackups -Force | Out-Null

        $composeBase = @("compose", "--env-file", $envFile, "-f", $composeFile, "-p", "growmaster")
        $databaseContainer = [string](& $script:DockerExecutable @composeBase ps -aq database 2>$null | Select-Object -First 1)
        $backendContainer = [string](& $script:DockerExecutable @composeBase ps -aq backend 2>$null | Select-Object -First 1)
        Write-MigrationLog "Stopping GrowMaster before storage migration to $targetRoot."
        Invoke-Docker ($composeBase + @("stop")) "GrowMasterja ni bilo mogoče varno ustaviti. Podatki niso bili premaknjeni."

        if ($databaseIsDirectory) {
            Copy-DirectoryVerified $databaseSource $stagingDatabase
        } else {
            if ([string]::IsNullOrWhiteSpace($databaseContainer)) {
                throw "Obstoječe Docker baze ni bilo mogoče najti. Stara baza je ostala nespremenjena."
            }
            Invoke-Docker @("cp", "${databaseContainer}:/var/lib/postgresql/data/.", $stagingDatabase) "Baze ni bilo mogoče kopirati iz Dockerja."
        }
        if ($backupIsDirectory) {
            Copy-DirectoryVerified $backupSource $stagingBackups
        } elseif (-not [string]::IsNullOrWhiteSpace($backendContainer)) {
            Invoke-Docker @("cp", "${backendContainer}:/data/backups/.", $stagingBackups) "Varnostnih kopij ni bilo mogoče kopirati iz Dockerja."
        }
        if (-not (Test-Path -LiteralPath (Join-Path $stagingDatabase "PG_VERSION"))) {
            throw "Kopirana mapa ne vsebuje veljavne PostgreSQL baze. Stara baza je ostala nespremenjena."
        }

        Move-Item -LiteralPath $stagingDatabase -Destination $databaseDestination
        Move-Item -LiteralPath $stagingBackups -Destination $backupDestination
        Remove-Item -LiteralPath $stagingRoot -Force

        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
        $environmentBackup = "$envFile.before-data-move-$timestamp"
        Set-GrowMasterEnvironmentValues $envFile @{
            POSTGRES_DATA_SOURCE = (Format-EnvironmentPath $databaseDestination)
            BACKUP_DATA_SOURCE = (Format-EnvironmentPath $backupDestination)
            GROWMASTER_DATA_ROOT = (Format-EnvironmentPath $targetRoot)
            GROWMASTER_WINDOWS_INSTALL = "true"
        } $environmentBackup
        $environmentUpdated = $true

        Invoke-Docker ($composeBase + @("up", "-d")) "GrowMasterja z novo mapo ni bilo mogoče zagnati."
        if (-not (Test-ApplicationHealth)) {
            throw "GrowMaster se z novo mapo ni uspešno zagnal."
        }
        Write-MigrationLog "Storage migration completed successfully. Previous data was retained as a recovery copy."
        Show-GrowMasterMessage (
            "Podatki so uspešno prestavljeni v:`n`n$targetRoot`n`n" +
            "GrowMaster je ponovno zagnan. Stara kopija je zaradi varnosti ostala na prejšnjem mestu."
        ) "Selitev je končana" | Out-Null
    } catch {
        Write-MigrationLog "ERROR: $($_.Exception.Message)"
        if ($environmentUpdated -and $environmentBackup -and (Test-Path -LiteralPath $environmentBackup)) {
            try {
                if ($composeBase) { & $script:DockerExecutable @composeBase stop | Out-Null }
                Copy-Item -LiteralPath $environmentBackup -Destination $envFile -Force
                if ($composeBase) { & $script:DockerExecutable @composeBase up -d | Out-Null }
                Write-MigrationLog "Restored the previous environment after a failed migration."
            } catch {
                Write-MigrationLog "ERROR while restoring previous environment: $($_.Exception.Message)"
            }
        } elseif ($composeBase) {
            try { & $script:DockerExecutable @composeBase up -d | Out-Null } catch { }
        }
        Show-GrowMasterMessage (
            "$($_.Exception.Message)`n`nStari podatki niso bili izbrisani. Podrobnosti so v:`n$logFile"
        ) "Selitev ni uspela" ([System.Windows.MessageBoxButton]::OK) ([System.Windows.MessageBoxImage]::Error) | Out-Null
        exit 1
    } finally {
        if ($hasMutex) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

if ($SelfTest) {
    Invoke-SelfTest
    exit 0
}

Invoke-DataMigration
