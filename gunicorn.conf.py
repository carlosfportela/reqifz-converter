"""
gunicorn.conf.py — Configuração do Gunicorn para produção (OpenShift/Linux)

Uso:
    gunicorn -c gunicorn.conf.py app:app

Variáveis de ambiente reconhecidas:
    PORT              Porta de escuta (padrão: 8080 — porta padrão OpenShift)
    WEB_CONCURRENCY   Número de worker processes (padrão: 2×CPUs + 1)
    GUNICORN_THREADS  Threads por worker (padrão: 4)
    LOG_LEVEL         Nível de log: debug|info|warning|error (padrão: info)
"""

import os
import multiprocessing

# ---------------------------------------------------------------------------
# Bind
# OpenShift expõe a aplicação na porta 8080 por padrão.
# Em outros ambientes, defina a variável PORT conforme necessário.
# ---------------------------------------------------------------------------
_port = os.environ.get('PORT', '8080')
bind = f'0.0.0.0:{_port}'

# ---------------------------------------------------------------------------
# Workers e Threads
# worker_class=gthread — thread-based, sem dependência de gevent.
# Suportado em qualquer Linux/container sem pacotes extras.
# ---------------------------------------------------------------------------
_cpu_count = multiprocessing.cpu_count()
workers = int(os.environ.get('WEB_CONCURRENCY', (_cpu_count * 2) + 1))
worker_class = 'gthread'
threads = int(os.environ.get('GUNICORN_THREADS', 4))

# ---------------------------------------------------------------------------
# Timeouts
# timeout: tempo máximo para processar uma requisição.
# Ajustado para 600s pois conversões de arquivos grandes podem demorar.
# keepalive: tempo para manter conexões HTTP keep-alive abertas.
# ---------------------------------------------------------------------------
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 600))
keepalive = 5
graceful_timeout = 30

# ---------------------------------------------------------------------------
# Reciclagem de Workers
# Recicla cada worker após N requisições para evitar memory leaks graduais.
# O jitter evita que todos os workers reiniciem ao mesmo tempo.
# ---------------------------------------------------------------------------
max_requests = 1000
max_requests_jitter = 100

# ---------------------------------------------------------------------------
# Logging
# accesslog='-' e errorlog='-' enviam logs para stdout/stderr,
# padrão para containers (OpenShift coleta automaticamente).
# ---------------------------------------------------------------------------
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# ---------------------------------------------------------------------------
# Segurança
# Oculta a versão do Gunicorn no header Server
# ---------------------------------------------------------------------------
server_header = False
sendfile = True

# ---------------------------------------------------------------------------
# Hooks de ciclo de vida (para diagnóstico)
# ---------------------------------------------------------------------------
def on_starting(server):
    server.log.info(
        f"Gunicorn iniciando — workers={workers}, threads={threads}, "
        f"worker_class={worker_class}, timeout={timeout}s, porta={_port}"
    )

def worker_exit(server, worker):
    server.log.info(f"Worker {worker.pid} encerrado")
