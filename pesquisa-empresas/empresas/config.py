"""Caminhos, limites e parâmetros ajustáveis por variável de ambiente."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTADOS_DIR = Path(os.environ.get("EMPRESAS_RESULTADOS", ROOT / "resultados"))
ENTRADAS_DIR = Path(os.environ.get("EMPRESAS_ENTRADAS", ROOT / "entradas"))
CACHE_DB = Path(os.environ.get("EMPRESAS_CACHE", ROOT / "cache" / "cache.sqlite"))

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888").rstrip("/")

# Leitor r.jina.ai (gratuito, sem chave, ~20 req/min) para páginas que só renderizam com JavaScript.
# Recebe apenas a URL pública da página. Desative com EMPRESAS_JINA=0.
USAR_JINA = os.environ.get("EMPRESAS_JINA", "1") != "0"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
HTTP_TIMEOUT = 15.0
MAX_PAGINA_BYTES = 3_000_000
MAX_PAGINAS_SITE = 6

# Validade do cache (segundos)
TTL_BUSCA = 7 * 86400
TTL_PAGINA = 7 * 86400
TTL_CADASTRO = 30 * 86400

# Intervalo mínimo entre chamadas (segundos), compartilhado entre threads
INTERVALO = {
    "searxng": 1.5,
    "ddgs": 2.5,
    "jina": 3.5,
    "opencnpj": 0.4,
    "brasilapi": 0.6,
    "minhareceita": 1.0,
    "cnpja": 12.5,  # limite público: 5 por minuto
    "viacep": 0.6,
    "dominio": 1.0,  # entre páginas do mesmo site
}

WORKERS_PADRAO = 3
