[CmdletBinding()]
param(
    [ValidateRange(0, 10000)]
    [int]$Tail = 100,

    [switch]$NoFollow
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot ".env"

if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "O arquivo .env não foi encontrado na raiz do projeto."
}

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "O comando docker não está disponível no ambiente."
}

function Write-Legend {
    Write-Host "Legenda: " -NoNewline
    Write-Host "2xx/OK" -ForegroundColor Green -NoNewline
    Write-Host " | " -NoNewline
    Write-Host "3xx" -ForegroundColor DarkYellow -NoNewline
    Write-Host " | " -NoNewline
    Write-Host "4xx/WARNING" -ForegroundColor Yellow -NoNewline
    Write-Host " | " -NoNewline
    Write-Host "5xx/ERROR/CRITICAL" -ForegroundColor Red -NoNewline
    Write-Host " | " -NoNewline
    Write-Host "INFO" -ForegroundColor Cyan -NoNewline
    Write-Host " | " -NoNewline
    Write-Host "healthcheck" -ForegroundColor DarkGray
}

function Get-LogColor {
    param(
        [Parameter(Mandatory)]
        [string]$Message
    )

    if ($Message -match "\[(ERROR|CRITICAL)\]" -or
        $Message -match "WORKER TIMEOUT|Traceback|SystemExit|SIGKILL") {
        return "Red"
    }

    $statusMatch = [regex]::Match(
        $Message,
        '"\s(?<status>[1-5]\d{2})\s+(?:\d+|-)'
    )

    if ($statusMatch.Success) {
        $status = [int]$statusMatch.Groups["status"].Value

        if ($status -ge 500) {
            return "Red"
        }

        if ($status -ge 400) {
            return "Yellow"
        }

        if ($status -ge 300) {
            return "DarkYellow"
        }

        if ($Message -match '127\.0\.0\.1' -and
            $Message -match 'Python-urllib') {
            return "DarkGray"
        }

        return "Green"
    }

    if ($Message -match "\[WARNING\]") {
        return "Yellow"
    }

    if ($Message -match "\[INFO\]") {
        return "Cyan"
    }

    if ($Message -match "exited with code 0") {
        return "Green"
    }

    if ($Message -match "exited with code [1-9]\d*") {
        return "Red"
    }

    return "Gray"
}

function Write-HighlightedLogLine {
    param(
        [AllowEmptyString()]
        [string]$Line
    )

    $prefixMatch = [regex]::Match(
        $Line,
        '^(?<prefix>[^|]+\|)(?<message>.*)$'
    )

    if ($prefixMatch.Success) {
        $prefix = $prefixMatch.Groups["prefix"].Value
        $message = $prefixMatch.Groups["message"].Value
        Write-Host $prefix -ForegroundColor DarkCyan -NoNewline
        Write-Host $message -ForegroundColor (Get-LogColor $message)
        return
    }

    Write-Host $Line -ForegroundColor (Get-LogColor $Line)
}

$composeArguments = @(
    "compose"
    "--project-directory"
    $projectRoot
    "--env-file"
    $envFile
)

$runningServices = @(
    & docker @composeArguments ps --status running --services backend 2>$null
)

if ($LASTEXITCODE -ne 0) {
    throw "Não foi possível consultar o estado do backend no Docker Compose."
}

if ($runningServices -notcontains "backend") {
    throw "O backend não está em execução. Inicie a aplicação antes de acompanhar os logs."
}

$arguments = $composeArguments + @(
    "logs"
    "--no-color"
    "--tail"
    $Tail.ToString()
)

if (-not $NoFollow) {
    $arguments += "--follow"
}

$arguments += "backend"

Write-Legend
Write-Host "Pressione Ctrl+C para parar de acompanhar; o contêiner continuará em execução."

Push-Location $projectRoot
try {
    & docker @arguments 2>&1 | ForEach-Object {
        Write-HighlightedLogLine ([string]$_)
    }
    $dockerExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($dockerExitCode -ne 0) {
    throw "O acompanhamento dos logs terminou com código $dockerExitCode."
}