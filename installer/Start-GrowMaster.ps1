param(
    [switch]$Build,
    [switch]$NoBrowser,
    [string]$DataDirectory
)

$ErrorActionPreference = "Stop"
$appRoot = Join-Path $PSScriptRoot "app"
$composeFile = Join-Path $appRoot "docker-compose.yml"
$stateRoot = Join-Path $env:APPDATA "GrowMaster"
$envFile = Join-Path $stateRoot ".env"
$logFile = Join-Path $stateRoot "launcher.log"

function Write-LauncherLog([string]$Message) {
    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    "$(Get-Date -Format o) $Message" | Add-Content -LiteralPath $logFile -Encoding UTF8
}

function Show-GrowMasterMessage([string]$Message, [string]$Title = "GrowMaster") {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($Message, $Title) | Out-Null
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

function Ensure-PrivateEnvironment {
    if (Test-Path -LiteralPath $envFile) { return }
    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    $storageRoot = if ([string]::IsNullOrWhiteSpace($DataDirectory)) {
        Join-Path $env:LOCALAPPDATA "GrowMasterData"
    } else {
        [Environment]::ExpandEnvironmentVariables($DataDirectory.Trim())
    }
    $storageRoot = [IO.Path]::GetFullPath($storageRoot).TrimEnd('\', '/')
    $databaseStorage = Join-Path $storageRoot "database"
    $backupStorage = Join-Path $storageRoot "backups"
    New-Item -ItemType Directory -Path $databaseStorage -Force | Out-Null
    New-Item -ItemType Directory -Path $backupStorage -Force | Out-Null
    $databaseSource = $databaseStorage.Replace('\', '/').Replace('$', '$$').Replace('"', '\"')
    $backupSource = $backupStorage.Replace('\', '/').Replace('$', '$$').Replace('"', '\"')
    $random = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Fill($random)
    $password = [Convert]::ToBase64String($random).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    @(
        "POSTGRES_DB=growmaster",
        "POSTGRES_USER=growmaster",
        "POSTGRES_PASSWORD=$password",
        "DATABASE_URL=postgresql+psycopg://growmaster:$password@database:5432/growmaster",
        "POSTGRES_DATA_SOURCE=`"$databaseSource`"",
        "BACKUP_DATA_SOURCE=`"$backupSource`"",
        "BACKUP_DIR=/data/backups",
        "COOKIE_SECURE=false",
        "CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost,https://localhost,capacitor://localhost"
    ) | Set-Content -LiteralPath $envFile -Encoding UTF8
    Write-LauncherLog "Created a private environment file and data directories under $storageRoot."
}

try {
    if (-not (Test-Path -LiteralPath $composeFile)) {
        throw "Namestitev GrowMasterja ni popolna. Ponovno zaženi namestitveno datoteko."
    }
    $docker = Find-DockerExecutable
    if (-not $docker) {
        Show-GrowMasterMessage "GrowMaster potrebuje Docker Desktop. Odprla se bo uradna stran za namestitev. Ko Docker namestiš in zaženeš, ponovno klikni ikono GrowMaster." "Potreben je Docker Desktop"
        Start-Process "https://docs.docker.com/desktop/setup/install/windows-install/"
        exit 2
    }

    Ensure-PrivateEnvironment
    $desktopCandidates = @(
        (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Docker\Docker\Docker Desktop.exe")
    )
    if (-not (& $docker info 2>$null)) {
        $desktop = $desktopCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if ($desktop) {
            Write-LauncherLog "Starting Docker Desktop."
            Start-Process -FilePath $desktop -WindowStyle Hidden
        }
        $deadline = (Get-Date).AddMinutes(3)
        do {
            Start-Sleep -Seconds 3
            $dockerReady = & $docker info 2>$null
        } until ($dockerReady -or (Get-Date) -gt $deadline)
        if (-not $dockerReady) { throw "Docker Desktop se ni pravočasno zagnal. Odpri ga ročno in poskusi znova." }
    }

    $composeBase = @("compose", "--env-file", $envFile, "-f", $composeFile, "-p", "growmaster")
    $composeArguments = $composeBase + @("up", "-d")
    $runningFrontend = & $docker @composeBase ps --status running -q frontend 2>$null
    if ($Build -or -not $runningFrontend) {
        if ($Build) { $composeArguments += "--build" }
        Write-LauncherLog "Starting GrowMaster services."
        & $docker @composeArguments | Out-File -LiteralPath $logFile -Append -Encoding UTF8
        if ($LASTEXITCODE -ne 0) { throw "GrowMasterja ni bilo mogoče zagnati. Podrobnosti so v $logFile" }
    }

    $healthy = $false
    $deadline = (Get-Date).AddMinutes(3)
    do {
        try {
            $health = Invoke-RestMethod -Uri "http://localhost:3000/api/health" -TimeoutSec 4
            $healthy = $health.status -eq "running"
        } catch { Start-Sleep -Seconds 2 }
    } until ($healthy -or (Get-Date) -gt $deadline)
    if (-not $healthy) { throw "GrowMaster se zaganja predolgo. Ponovno klikni ikono čez minuto." }
    if (-not $NoBrowser) { Start-Process "http://localhost:3000/" }
    Write-LauncherLog "GrowMaster is ready."
} catch {
    Write-LauncherLog "ERROR: $($_.Exception.Message)"
    Show-GrowMasterMessage $_.Exception.Message "GrowMaster se ni zagnal"
    exit 1
}
