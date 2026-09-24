[CmdletBinding()]
param(
    [switch]$SimulateValidationFailure
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$composeFile = Join-Path $projectRoot "compose.test.yml"

if (-not (Test-Path -LiteralPath $composeFile -PathType Leaf)) {
    throw "O arquivo compose.test.yml não foi encontrado na raiz do projeto."
}

if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "O comando docker não está disponível no ambiente."
}

$previousSimulation = Get-Item Env:TEST_SIMULATE_VALIDATION_FAILURE `
    -ErrorAction SilentlyContinue
$executionCode = 1
$cleanupCode = 0
$caughtError = $null

try {
    $env:TEST_SIMULATE_VALIDATION_FAILURE = if (
        $SimulateValidationFailure
    ) { "1" } else { "0" }

    Write-Host "Criando o ambiente MySQL isolado e executando a validação..."
    $nativeErrorPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & docker compose `
            --file $composeFile `
            up `
            --build `
            --abort-on-container-exit `
            --exit-code-from backend-test `
            backend-test
        $executionCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $nativeErrorPreference
    }
}
catch {
    $caughtError = $_
}
finally {
    Write-Host "Removendo contêineres, rede e volume exclusivos dos testes..."
    $nativeErrorPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & docker compose `
            --file $composeFile `
            down `
            --volumes `
            --remove-orphans
        $cleanupCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $nativeErrorPreference
    }

    if ($null -eq $previousSimulation) {
        Remove-Item Env:TEST_SIMULATE_VALIDATION_FAILURE `
            -ErrorAction SilentlyContinue
    }
    else {
        $env:TEST_SIMULATE_VALIDATION_FAILURE = $previousSimulation.Value
    }
}

if ($cleanupCode -ne 0) {
    throw "A limpeza do ambiente MySQL de teste falhou com código $cleanupCode."
}

if ($null -ne $caughtError) {
    throw $caughtError
}

if ($executionCode -ne 0) {
    [Console]::Error.WriteLine(
        "A validação MySQL falhou com código $executionCode."
    )
    exit $executionCode
}

Write-Host "Validação MySQL concluída e ambiente descartável removido."
