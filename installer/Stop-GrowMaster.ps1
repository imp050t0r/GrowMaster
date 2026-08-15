$ErrorActionPreference = "SilentlyContinue"
$envFile = Join-Path (Join-Path $env:APPDATA "GrowMaster") ".env"
$composeFile = Join-Path (Join-Path $PSScriptRoot "app") "docker-compose.yml"
$docker = Get-Command docker.exe -ErrorAction SilentlyContinue
if ($docker -and (Test-Path -LiteralPath $envFile) -and (Test-Path -LiteralPath $composeFile)) {
    & $docker.Source compose --env-file $envFile -f $composeFile -p growmaster stop | Out-Null
}
