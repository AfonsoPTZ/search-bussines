"""Utilitários: normalização de texto, comparação de nomes, domínios, limitador de ritmo e cache."""

import json
import re
import sqlite3
import threading
import time
import unicodedata
from urllib.parse import urlparse

import tldextract
from rapidfuzz import fuzz

from empresas import config

# Usa a lista de sufixos embutida no pacote, sem baixar nada da internet.
_tld = tldextract.TLDExtract(suffix_list_urls=())

# Palavras que não ajudam a distinguir empresas.
STOPWORDS = {
    "ltda", "me", "epp", "eireli", "sa", "s", "a", "cia", "companhia", "comercio", "comercial",
    "industria", "servicos", "de", "da", "do", "das", "dos", "e", "em", "the", "and", "loja",
    "lojas", "empresa", "grupo", "oficial", "brasil", "br", "unipessoal", "limitada", "mei",
}

UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
    "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}


_UF_POR_NOME = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA", "mato grosso": "MT",
    "mato grosso do sul": "MS", "minas gerais": "MG", "para": "PA", "paraiba": "PB", "parana": "PR",
    "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR", "santa catarina": "SC", "sao paulo": "SP",
    "sergipe": "SE", "tocantins": "TO",
}


def sigla_uf(texto: str | None) -> str:
    """'São Paulo' -> 'SP', 'sp' -> 'SP', 'BR-SP' -> 'SP'; vazio se não reconhecer."""
    if not texto:
        return ""
    t = texto.strip().upper().removeprefix("BR-")
    if t in UFS:
        return t
    return _UF_POR_NOME.get(normalizar(texto), "")


def sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def normalizar(texto: str | None) -> str:
    """Minúsculas, sem acentos e sem pontuação."""
    if not texto:
        return ""
    t = sem_acentos(texto).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def tokens_nome(texto: str | None) -> list[str]:
    return [t for t in normalizar(texto).split() if t not in STOPWORDS and len(t) > 1]


def similaridade(a: str | None, b: str | None) -> float:
    """0-100. Compara nomes ignorando termos societários (LTDA, ME, comércio de...)."""
    ta, tb = " ".join(tokens_nome(a)), " ".join(tokens_nome(b))
    if not ta or not tb:
        return 0.0
    # Média de set (ignora ordem/repetição) e sort (penaliza palavras a mais): "Kopenhagen" x
    # "Kopenhagen Mario Ferraz" (loja franqueada) não deve contar como nome idêntico.
    media = (fuzz.token_set_ratio(ta, tb) + fuzz.token_sort_ratio(ta, tb)) / 2
    return max(media, fuzz.ratio(ta.replace(" ", ""), tb.replace(" ", "")))


def contido_com_extras(procurado: str | None, candidato: str | None) -> bool:
    """True se o candidato é o nome procurado + palavras a mais (ex.: marca + unidade)."""
    tp, tc = set(tokens_nome(procurado)), set(tokens_nome(candidato))
    return bool(tp) and tp < tc and len(tc - tp) >= 2


def compacto(texto: str | None) -> str:
    return "".join(tokens_nome(texto))


def dominio(url: str | None) -> str:
    """Domínio registrável: https://www.loja.com.br/x -> loja.com.br"""
    if not url:
        return ""
    if "://" not in url:
        url = "http://" + url
    ext = _tld(url)
    if not ext.domain:
        return urlparse(url).hostname or ""
    return f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain


def rotulo_dominio(url: str | None) -> str:
    """Parte principal do domínio: https://www.loja-x.com.br -> lojax"""
    if not url:
        return ""
    if "://" not in url:
        url = "http://" + url
    return re.sub(r"[^a-z0-9]", "", _tld(url).domain.lower())


def unicos(itens):
    vistos, saida = set(), []
    for i in itens:
        if i and i not in vistos:
            vistos.add(i)
            saida.append(i)
    return saida


class Ritmo:
    """Garante um intervalo mínimo entre chamadas para cada chave (provedor ou domínio)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._proximo: dict[str, float] = {}
        self._locks: dict[str, threading.Lock] = {}

    def _lock_de(self, chave):
        with self._lock:
            return self._locks.setdefault(chave, threading.Lock())

    def esperar(self, chave: str, intervalo: float):
        with self._lock_de(chave):
            agora = time.monotonic()
            alvo = self._proximo.get(chave, 0.0)
            if alvo > agora:
                time.sleep(alvo - agora)
            self._proximo[chave] = time.monotonic() + intervalo


ritmo = Ritmo()


class Cache:
    """Cache em SQLite (buscas, páginas e consultas de CNPJ) para não repetir requisições."""

    def __init__(self, caminho=None):
        caminho = caminho or config.CACHE_DB
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(caminho), check_same_thread=False, timeout=30)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cache (chave TEXT PRIMARY KEY, valor TEXT, criado REAL)"
        )
        self._lock = threading.Lock()

    def obter(self, chave: str, ttl: float):
        with self._lock:
            linha = self._db.execute(
                "SELECT valor, criado FROM cache WHERE chave = ?", (chave,)
            ).fetchone()
        if linha and time.time() - linha[1] < ttl:
            return json.loads(linha[0])
        return None

    def gravar(self, chave: str, valor):
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
                (chave, json.dumps(valor, ensure_ascii=False), time.time()),
            )
            self._db.commit()


_cache = None
_cache_lock = threading.Lock()


def cache() -> Cache:
    global _cache
    with _cache_lock:
        if _cache is None:
            _cache = Cache()
        return _cache
