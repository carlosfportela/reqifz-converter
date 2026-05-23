# =============================================================================
# start_prod_local.ps1 — Inicia a aplicação em modo produção no Windows
#
# Usa Waitress como servidor WSGI (Gunicorn não suporta Windows nativamente).
# Útil para simular o comportamento de produção antes de fazer deploy no OpenShift.
#
# Uso:
#   .\start_prod_local.ps1
#
# Pré-requisitos:
#   pip install -r requirements.txt
# =============================================================================

Write-Host ""
Write-Host "  🚀  Modo: PRODUÇÃO LOCAL (Waitress)" -ForegroundColor Cyan
Write-Host "  📍  Acesse: http://localhost:8080" -ForegroundColor Cyan
Write-Host "  ℹ   Para desenvolvimento com hot-reload: python app.py" -ForegroundColor Yellow
Write-Host ""

# Carrega o .env se existir (variáveis de ambiente de desenvolvimento)
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Write-Host "  📄  Carregando variáveis de: .env" -ForegroundColor DarkGray
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)\s*=\s*(.*)\s*$') {
            $name  = $Matches[1].Trim()
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            [System.Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
    }
}

# Garante que não estará em modo debug
$env:FLASK_ENV = "production"

# Configurações do servidor
$port    = if ($env:PORT) { $env:PORT } else { "8080" }
$threads = if ($env:GUNICORN_THREADS) { $env:GUNICORN_THREADS } else { "8" }

Write-Host "  ⚙   Threads: $threads | Porta: $port" -ForegroundColor DarkGray
Write-Host ""

# Inicia o Waitress
# --threads: número de threads para requisições concorrentes
# --connection-limit: máximo de conexões simultâneas aceitas
# --channel-timeout: tempo máximo para completar uma requisição (segundos)
python -m waitress `
    --host=0.0.0.0 `
    --port=$port `
    --threads=$threads `
    --connection-limit=100 `
    --channel-timeout=600 `
    --ident="" `
    app:app
