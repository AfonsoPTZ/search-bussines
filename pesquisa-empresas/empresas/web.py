"""Busca na web (SearXNG local, com contingência via ddgs) e leitura de páginas com cache."""

import threading
import urllib.robotparser
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

import httpx

from empresas import config
from empresas.util import cache, ritmo

_HEADERS = {
    "User-Agent": config.USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
}

_local = threading.local()


def cliente(verificar_ssl: bool = True) -> httpx.Client:
    """Um cliente HTTP por thread (e um separado, sem verificação SSL, só para páginas com certificado inválido)."""
    nome = "cliente" if verificar_ssl else "cliente_sem_ssl"
    if not hasattr(_local, nome):
        setattr(_local, nome, httpx.Client(
            headers=_HEADERS, timeout=config.HTTP_TIMEOUT, follow_redirects=True, verify=verificar_ssl
        ))
    return getattr(_local, nome)


@dataclass
class Resultado:
    url: str
    titulo: str
    trecho: str
    motor: str


# ----------------------------------------------------------------------------- busca

_searxng_ok: bool | None = None
_searxng_lock = threading.Lock()


def searxng_disponivel() -> bool:
    global _searxng_ok
    with _searxng_lock:
        if _searxng_ok is None:
            try:
                r = httpx.get(f"{config.SEARXNG_URL}/healthz", timeout=3)
                _searxng_ok = r.status_code == 200
            except httpx.HTTPError:
                _searxng_ok = False
        return _searxng_ok


def _buscar_searxng(consulta: str, maximo: int) -> list[Resultado]:
    ritmo.esperar("searxng", config.INTERVALO["searxng"])
    r = cliente().get(
        f"{config.SEARXNG_URL}/search",
        params={"q": consulta, "format": "json", "language": "pt-BR", "safesearch": 0},
        timeout=25,
    )
    r.raise_for_status()
    dados = r.json()
    return [
        Resultado(x.get("url", ""), x.get("title", ""), x.get("content", ""), "searxng:" + ",".join(x.get("engines", [])))
        for x in dados.get("results", [])[:maximo]
    ]


def _buscar_ddgs(consulta: str, maximo: int) -> list[Resultado]:
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException

    for backend in ("bing", "yahoo", "duckduckgo", "auto"):
        ritmo.esperar("ddgs", config.INTERVALO["ddgs"])
        try:
            itens = DDGS(timeout=10).text(consulta, region="br-pt", max_results=maximo, backend=backend)
        except DDGSException:
            continue
        except Exception:  # falhas de rede/parse de um backend não devem derrubar a busca
            continue
        if itens:
            return [Resultado(i.get("href", ""), i.get("title", ""), i.get("body", ""), f"ddgs:{backend}") for i in itens]
    return []


def buscar(consulta: str, maximo: int = 10) -> list[Resultado]:
    """Busca com cache. Tenta SearXNG local e cai para ddgs se estiver indisponível ou vazio."""
    chave = f"busca:{consulta}:{maximo}"
    em_cache = cache().obter(chave, config.TTL_BUSCA)
    if em_cache is not None:
        return [Resultado(**x) for x in em_cache]

    resultados: list[Resultado] = []
    if searxng_disponivel():
        try:
            resultados = _buscar_searxng(consulta, maximo)
        except (httpx.HTTPError, ValueError):
            resultados = []
    if not resultados:
        resultados = _buscar_ddgs(consulta, maximo)
    if resultados:  # não guarda resultado vazio: pode ter sido bloqueio temporário
        cache().gravar(chave, [asdict(x) for x in resultados])
    return resultados


# ----------------------------------------------------------------------------- páginas

_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_robots_lock = threading.Lock()


def permitido(url: str) -> bool:
    """Respeita robots.txt do site (sem robots.txt acessível = permitido)."""
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    with _robots_lock:
        if base not in _robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = cliente().get(base + "/robots.txt", timeout=8)
                if r.status_code == 200 and "text" in r.headers.get("content-type", "text"):
                    rp.parse(r.text.splitlines())
                    _robots[base] = rp
                else:
                    _robots[base] = None
            except (httpx.HTTPError, httpx.InvalidURL, UnicodeError, ValueError):
                _robots[base] = None
        rp = _robots[base]
    return rp is None or rp.can_fetch(config.USER_AGENT, url) or rp.can_fetch("*", url)


@dataclass
class Pagina:
    url: str
    url_final: str
    status: int
    html: str
    via: str = "direto"
    erro: str = ""


def baixar(url: str, usar_cache: bool = True) -> Pagina:
    chave = f"pagina:{url}"
    if usar_cache:
        em_cache = cache().obter(chave, config.TTL_PAGINA)
        if em_cache is not None:
            return Pagina(**em_cache)

    if not permitido(url):
        return Pagina(url, url, 0, "", erro="bloqueado por robots.txt")

    host = urlparse(url).hostname or ""
    ritmo.esperar(f"dominio:{host}", config.INTERVALO["dominio"])
    pagina = None
    for verificar_ssl in (True, False):
        try:
            c = cliente() if verificar_ssl else cliente(verificar_ssl=False)
            c.cookies.clear()  # não precisamos de sessão; cookies malformados de um site quebrariam o próximo
            with c.stream("GET", url) as r:
                corpo = b""
                for parte in r.iter_bytes():
                    corpo += parte
                    if len(corpo) > config.MAX_PAGINA_BYTES:
                        break
                tipo = r.headers.get("content-type", "")
                html = corpo.decode(r.encoding or "utf-8", errors="replace") if "html" in tipo or "text" in tipo or not tipo else ""
                pagina = Pagina(url, str(r.url), r.status_code, html)
            break
        except httpx.ConnectError as e:
            # Sites pequenos com certificado vencido: tenta de novo sem verificar SSL (só leitura de página pública).
            if verificar_ssl and "CERTIFICATE" in str(e).upper():
                continue
            pagina = Pagina(url, url, 0, "", erro=f"conexão: {e}"[:200])
            break
        except (httpx.HTTPError, httpx.InvalidURL, UnicodeError, ValueError) as e:
            pagina = Pagina(url, url, 0, "", erro=f"{type(e).__name__}: {e}"[:200])
            break

    if pagina and pagina.status == 200 and pagina.html:
        cache().gravar(chave, asdict(pagina))
    return pagina


def baixar_via_leitor(url: str) -> Pagina | None:
    """Usa r.jina.ai para renderizar páginas que dependem de JavaScript (retorna markdown)."""
    if not config.USAR_JINA:
        return None
    chave = f"jina:{url}"
    em_cache = cache().obter(chave, config.TTL_PAGINA)
    if em_cache is not None:
        return Pagina(**em_cache)
    ritmo.esperar("jina", config.INTERVALO["jina"])
    try:
        r = cliente().get(f"https://r.jina.ai/{url}", timeout=40, headers={"Accept": "text/plain"})
    except httpx.HTTPError:
        return None
    if r.status_code != 200 or len(r.text) < 200:
        return None
    pagina = Pagina(url, url, 200, r.text, via="r.jina.ai")
    cache().gravar(chave, asdict(pagina))
    return pagina

