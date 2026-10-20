"""Normalização de identificadores usados para reconhecer a mesma empresa em pesquisas diferentes.

Chaves fortes (unem pesquisas automaticamente, salvo conflito de CNPJ):
    cnpj:<14 caracteres>   CNPJ confirmado
    ig:<usuario>           @ informado na entrada ou confirmado (site oficial que linka o perfil, revisão)
    dom:<domínio>          site oficial confirmado
Chave de entrada (mesmo pedido de pesquisa repetido, ex.: "Atualizar"):
    ent:<texto normalizado da entrada>
Nomes parecidos nunca unem nada: só geram sugestão de duplicidade para revisão.
"""

import re
from urllib.parse import urlparse

from empresas import cnpj as cnpjlib
from empresas.util import dominio as dominio_registravel
from empresas.util import normalizar as _normalizar
from empresas.util import tokens_nome

# Hospedagens compartilhadas: o domínio registrável é de milhares de sites, então a chave usa o host completo.
COMPARTILHADOS = {
    "wixsite.com", "wix.com", "blogspot.com", "wordpress.com", "negocio.site", "business.site", "ueniweb.com",
    "webnode.com", "webnode.com.br", "weebly.com", "jimdosite.com", "jimdo.com", "site123.me", "godaddysites.com",
    "squarespace.com", "webflow.io", "github.io", "netlify.app", "vercel.app", "myshopify.com", "carrd.co",
    "canva.site", "my.canva.site", "lojavirtualnuvem.com.br", "mercadoshops.com.br", "linktr.ee", "linkbio.co",
    "beacons.ai", "taplink.cc", "lnk.bio", "sites.google.com", "google.com", "wa.me", "instagram.com",
    "facebook.com", "bit.ly", "abre.ai", "comunidades.net", "loja2.com.br", "tray.com.br", "yampi.com.br",
}
_SEM_IDENTIDADE = {"linktr.ee", "linkbio.co", "beacons.ai", "taplink.cc", "lnk.bio", "wa.me", "instagram.com",
                   "facebook.com", "bit.ly", "abre.ai", "google.com", "api.whatsapp.com", "whatsapp.com", "youtube.com"}


def texto(t: str | None) -> str:
    """Minúsculas, sem acentos e sem pontuação (para busca)."""
    return _normalizar(t)


def chave_dominio(url: str | None) -> str:
    """Domínio que identifica o site: registrável (loja.com.br), ou o host inteiro em hospedagem compartilhada."""
    if not url:
        return ""
    bruto = url if "://" in url else "http://" + url
    host = (urlparse(bruto).hostname or "").lower().removeprefix("www.")
    if not host:
        return ""
    reg = dominio_registravel(bruto).lower()
    if reg in _SEM_IDENTIDADE or host in _SEM_IDENTIDADE:
        return ""
    if reg in COMPARTILHADOS or any(host.endswith("." + c) or host == c for c in COMPARTILHADOS):
        # fulano.wixsite.com/empresa e sites.google.com/view/empresa: o caminho também identifica o site
        partes = [p for p in urlparse(bruto).path.lower().split("/") if p]
        if host == "sites.google.com" and len(partes) >= 2:
            return f"{host}/{partes[0]}/{partes[1]}"
        if reg == "wixsite.com" and partes:
            return f"{host}/{partes[0]}"
        return host
    return reg


def handle_de_url(url: str | None) -> str:
    """https://www.instagram.com/Fulano/ -> fulano ('' se não for perfil)."""
    from prospeccao.arrobas import ArrobaInvalida, normalizar
    if not url:
        return ""
    try:
        return normalizar(url)
    except ArrobaInvalida:
        return ""


def cnpj(valor: str | None) -> str:
    return cnpjlib.limpar(valor or "") if valor else ""


def chave_nome(nome: str | None) -> str:
    """Nome sem termos societários/genéricos, para sugerir duplicidades (nunca para unir)."""
    return " ".join(tokens_nome(nome))


def entrada(texto_entrada: str | None) -> str:
    return " ".join(_normalizar(texto_entrada).split())


def cidade_para_pesquisa(cidade: str | None) -> str:
    """Cidade do perfil do Instagram ("Alpestre, Rio Grande do Sul") no formato da lista de empresas ("Alpestre/RS")."""
    from empresas.util import sigla_uf
    t = re.sub(r"[|;\t]+", " ", cidade or "").strip()
    if "," in t:
        nome, _, estado = t.partition(",")
        uf = sigla_uf(estado.strip())
        if uf:
            return f"{nome.strip()}/{uf}"
        return nome.strip()
    return t


_TELEFONE = re.compile(r"\(?\+?\d[\d\s().-]{6,}\d\)?")


def nome_para_pesquisa(nome: str | None) -> str:
    """Nome de perfil pronto para a lista de empresas: sem telefones, emojis e separadores da lista."""
    t = _TELEFONE.sub(" ", nome or "")
    t = re.sub(r"[|;\t]+", " ", t)
    t = "".join(c for c in t if c.isalnum() or c in " .,&'-/()")
    t = re.sub(r"\s+", " ", t).strip(" -/.,")
    return t[:80]
