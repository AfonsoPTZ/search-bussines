"""Extração de contatos e identificadores de páginas HTML e de trechos de texto."""

import html
import json
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from empresas import cnpj as cnpjlib
from empresas.categorias import e_organizacao
from empresas.util import dominio, sem_acentos, sigla_uf, unicos

DDDS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38, 41, 42,
    43, 44, 45, 46, 47, 48, 49, 51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 73, 74,
    75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 92, 93, 94, 95, 96, 97, 98, 99,
}

_RE_EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,10}\b")
_EMAIL_IGNORAR = re.compile(
    r"\.(png|jpe?g|gif|webp|svg|css|js)$|@(\d+x|sentry|.*wixpress|example\.|exemplo\.|email\.com$|dominio\.|seudominio)",
    re.I,
)
# Telefone com DDD e separador antes dos 4 últimos dígitos: (14) 3222-1234, 14 99876-5432, +55 11 3333 4444
_RE_FONE = re.compile(
    r"(?<![\d/.,-])(?:\+?55[\s.-]?)?(?:\((\d{2})\)|(\d{2}))[\s.-]?(9?\s?\d{4})[\s.-](\d{4})(?![\d])"
)
_RE_0800 = re.compile(r"\b(0[38]00)[\s.-]?(\d{3})[\s.-]?(\d{4})\b")
_RE_4004 = re.compile(r"(?<![\d-])((?:3003|4000|4001|4002|4003|4004|4020|4062))[\s.-](\d{4})(?![\d])")
_RE_CEP = re.compile(r"(?<![\d.])(\d{2}\.?\d{3})-(\d{3})(?!\d)|CEP[:\s]*(\d{8})(?!\d)", re.I)
# Logradouro + nome curto + número, com complemento curto opcional (ex.: "Rua X, 123 - Centro, Bauru - SP").
_RE_ENDERECO = re.compile(
    r"\b(?:Rua|R\.|Avenida|Av\.|Alameda|Al\.|Rodovia|Rod\.|Travessa|Tv\.|Pra[çc]a|Estrada|Largo)\s"
    r"[^\n|•().;:!?\d]{2,60}?,?\s*(?:n[º°o.]*\s*)?\d{1,5}\b(?:[^\n|•();:!?]{0,70})?",
    re.I,
)

_SOCIAL_IGNORAR = {
    "instagram": {"p", "reel", "reels", "explore", "stories", "accounts", "tv", "about", "developer", "legal", "direct", "share"},
    "facebook": {"sharer", "sharer.php", "share", "plugins", "tr", "dialog", "login", "groups", "watch", "events", "policies", "help", "profile.php", "pages", "hashtag", "story.php", "photo.php"},
}


@dataclass
class Achados:
    emails: list[str] = field(default_factory=list)
    telefones: list[str] = field(default_factory=list)
    whatsapp: list[str] = field(default_factory=list)
    instagram: list[str] = field(default_factory=list)
    facebook: list[str] = field(default_factory=list)
    linkedin: list[str] = field(default_factory=list)
    outros: list[str] = field(default_factory=list)
    cnpjs: list[str] = field(default_factory=list)
    ceps: list[str] = field(default_factory=list)
    enderecos: list[str] = field(default_factory=list)
    horarios: list[str] = field(default_factory=list)
    avaliacoes: list[str] = field(default_factory=list)
    jsonld: list[dict] = field(default_factory=list)

    def juntar(self, outro: "Achados"):
        for nome in self.__dataclass_fields__:
            setattr(self, nome, unicos(getattr(self, nome) + getattr(outro, nome)) if nome != "jsonld"
                    else getattr(self, nome) + getattr(outro, nome))


# "964K Followers", "1,791 Followers", "5M seguidores", "714 mil seguidores", "1,2 mi seguidores"
_RE_SEGUIDORES = re.compile(
    r"(\d[\d.,]*)\s*(mil|mi|milh[õo]es|milh[ãa]o|[kKmM])?\s*(?:seguidores|followers)\b", re.I)
_MULTIPLICADOR = {"k": 1_000, "mil": 1_000, "m": 1_000_000, "mi": 1_000_000, "milhoes": 1_000_000, "milhao": 1_000_000}


def seguidores_em(texto: str | None) -> int | None:
    """Número de seguidores mostrado no perfil (ou no trecho do buscador). Aproximado: o Instagram arredonda."""
    m = _RE_SEGUIDORES.search(texto or "")
    if not m:
        return None
    numero, sufixo = m.group(1).strip(".,"), sem_acentos((m.group(2) or "").lower())
    try:
        if sufixo:
            return int(float(numero.replace(",", ".")) * _MULTIPLICADOR[sufixo])
        return int(re.sub(r"[.,]", "", numero))
    except (ValueError, KeyError):
        return None


# Horário publicado em texto: dia(s) + duas horas ("Segunda a sábado: 11h40 às 22h", "Seg-Sex 08:00 - 18:00").
_DIA = (r"(?:seg(?:unda)?|ter(?:[çc]a)?|qua(?:rta)?|qui(?:nta)?|sex(?:ta)?|s[áa]b(?:ado)?|dom(?:ingo)?|feriados?"
        r"|diariamente|todos\s+os\s+dias)s?(?:[\s-]*feiras?)?\.?")
_HORA = r"\d{1,2}\s?(?:h|:|hs)\s?\d{0,2}(?:\s?min(?:utos|h)?)?"
_RE_HORARIO = re.compile(rf"\b{_DIA}[^\n\d]{{0,40}}?\b{_HORA}[^\n\d]{{0,15}}?{_HORA}", re.I)
_DIAS_SCHEMA = {"monday": "seg", "tuesday": "ter", "wednesday": "qua", "thursday": "qui", "friday": "sex",
                "saturday": "sáb", "sunday": "dom", "mo": "seg", "tu": "ter", "we": "qua", "th": "qui",
                "fr": "sex", "sa": "sáb", "su": "dom"}


def horarios_em(texto: str | None) -> list[str]:
    """Trechos de horário de funcionamento/atendimento. Trechos vizinhos viram um só."""
    texto = (texto or "").replace("​", "")
    grupos, atual, fim = [], [], -999
    for m in _RE_HORARIO.finditer(texto):
        trecho = " ".join(m.group(0).split()).strip(" ,;:-")
        if atual and m.start() - fim <= 25:
            atual.append(trecho)
        else:
            if atual:
                grupos.append("; ".join(atual))
            atual = [trecho]
        fim = m.end()
    if atual:
        grupos.append("; ".join(atual))
    return unicos(g[:200] for g in grupos)[:3]


def horario_jsonld(org: dict) -> str:
    def dia(d):
        d = str(d).rstrip("/").split("/")[-1].lower()
        return _DIAS_SCHEMA.get(d, d)

    oh = org.get("openingHours")
    if isinstance(oh, str):
        oh = [oh]
    if isinstance(oh, list) and oh:
        return "; ".join(str(x) for x in oh if x)[:200]
    spec = org.get("openingHoursSpecification")
    spec = spec if isinstance(spec, list) else [spec] if isinstance(spec, dict) else []
    partes = []
    for s in spec:
        if not isinstance(s, dict) or not s.get("opens"):
            continue
        dias = s.get("dayOfWeek")
        dias = dias if isinstance(dias, list) else [dias]
        partes.append(f"{'/'.join(dia(d) for d in dias if d)} {str(s['opens'])[:5]}–{str(s.get('closes', ''))[:5]}")
    return "; ".join(partes)[:200]


def avaliacao_jsonld(org: dict) -> str:
    ar = org.get("aggregateRating")
    if not isinstance(ar, dict) or not ar.get("ratingValue"):
        return ""
    total = ar.get("reviewCount") or ar.get("ratingCount")
    melhor = ar.get("bestRating") or 5
    return f"{ar['ratingValue']} de {melhor}" + (f" ({total} avaliações)" if total else "")


def formatar_fone(ddd: str, numero: str) -> str | None:
    numero = re.sub(r"\D", "", numero)
    if not ddd.isdigit() or int(ddd) not in DDDS:
        return None
    if len(numero) == 9 and numero[0] == "9":
        return f"({ddd}) {numero[:5]}-{numero[5:]}"
    if len(numero) == 8 and numero[0] in "2345":
        return f"({ddd}) {numero[:4]}-{numero[4:]}"
    return None


def fone_de_digitos(digitos: str) -> str | None:
    d = re.sub(r"\D", "", digitos or "")
    if d.startswith("0800") and len(d) == 11:
        return f"0800 {d[4:7]} {d[7:]}"
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if d.startswith("0") and len(d) in (11, 12):
        d = d[1:]
    if len(d) in (10, 11):
        return formatar_fone(d[:2], d[2:])
    if len(d) == 8 and d[:4] in ("3003", "4000", "4001", "4002", "4003", "4004", "4020", "4062"):
        return f"{d[:4]}-{d[4:]}"
    return None


def telefones_em(texto: str) -> list[str]:
    saida = []
    for m in _RE_FONE.finditer(texto or ""):
        f = formatar_fone(m.group(1) or m.group(2), m.group(3) + m.group(4))
        if f:
            saida.append(f)
    for m in _RE_0800.finditer(texto or ""):
        saida.append(f"{m.group(1)} {m.group(2)} {m.group(3)}")
    for m in _RE_4004.finditer(texto or ""):
        saida.append(f"{m.group(1)}-{m.group(2)}")
    return unicos(saida)


# Créditos de quem fez o site ("Website design by Fulano fulano@gmail.com") não são contato da empresa.
_RE_CREDITO = re.compile(r"(desenvolvid[oa]|criad[oa]|feito|design|designed|developed|powered|made|produzid[oa])\s+(por|by|with)\b|ag[êe]ncia", re.I)


def emails_em(texto: str) -> list[str]:
    saida = []
    texto = texto or ""
    for m in _RE_EMAIL.finditer(texto):
        e = m.group(0).strip(".").lower()
        if _EMAIL_IGNORAR.search(e) or _RE_CREDITO.search(texto[max(0, m.start() - 80):m.start()]):
            continue
        saida.append(e)
    return unicos(saida)


def ceps_em(texto: str) -> list[str]:
    saida = []
    for m in _RE_CEP.finditer(texto or ""):
        if m.group(3):
            saida.append(f"{m.group(3)[:5]}-{m.group(3)[5:]}")
        else:
            saida.append(f"{m.group(1).replace('.', '')}-{m.group(2)}")
    return unicos(saida)


def enderecos_em(texto: str) -> list[str]:
    saida = []
    for m in _RE_ENDERECO.finditer(texto or ""):
        e = " ".join(m.group(0).split()).strip(" ,.-")
        if 10 <= len(e) <= 180:
            saida.append(e)
    return unicos(saida)[:5]


def whatsapp_de_url(url: str) -> str | None:
    """wa.me/5514999998888 ou api.whatsapp.com/send?phone=... -> telefone formatado."""
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if host in ("wa.me", "www.wa.me"):
        num = p.path.strip("/").split("/")[0]
        if num == "message":
            return None
    elif "whatsapp.com" in host:
        num = (parse_qs(p.query).get("phone") or [""])[0]
    else:
        return None
    return fone_de_digitos(num)


def classificar_link(url: str, achados: Achados):
    """Reconhece links de redes sociais, WhatsApp e telefone."""
    try:
        p = urlparse(url)
    except ValueError:
        return
    host = (p.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    partes = [x for x in p.path.split("/") if x]
    if p.scheme == "tel":
        f = fone_de_digitos(unquote(url[4:]))
        if f:
            achados.telefones.append(f)
    elif p.scheme == "mailto":
        achados.emails += emails_em(unquote(url[7:]).split("?")[0])
    elif host in ("wa.me", "api.whatsapp.com", "web.whatsapp.com", "whatsapp.com", "chat.whatsapp.com"):
        f = whatsapp_de_url(url)
        if f:
            achados.whatsapp.append(f)
        elif host == "wa.me" and partes[:1] == ["message"]:
            achados.outros.append(url)
    elif host.endswith("instagram.com") and partes and partes[0].lower() not in _SOCIAL_IGNORAR["instagram"]:
        achados.instagram.append(f"https://www.instagram.com/{partes[0].lower()}/")
    elif (host.endswith("facebook.com") or host == "fb.com") and partes and partes[0].lower() not in _SOCIAL_IGNORAR["facebook"]:
        achados.facebook.append(f"https://www.facebook.com/{partes[0]}/")
    elif host.endswith("linkedin.com") and len(partes) >= 2 and partes[0] in ("company", "school"):
        achados.linkedin.append(f"https://www.linkedin.com/{partes[0]}/{partes[1]}/")
    elif host in ("youtube.com", "tiktok.com", "x.com", "twitter.com", "linktr.ee", "threads.net", "pinterest.com") and partes:
        if partes[0] not in ("share", "intent", "watch", "embed", "hashtag", "home"):
            achados.outros.append(f"https://{host}/{'/'.join(partes[:2])}")


def de_texto(texto: str) -> Achados:
    """Extração a partir de texto puro (ex.: trechos de resultados de busca)."""
    a = Achados()
    a.emails = emails_em(texto)
    a.telefones = telefones_em(texto)
    a.cnpjs = cnpjlib.encontrar(texto)
    a.ceps = ceps_em(texto)
    a.enderecos = enderecos_em(texto)
    a.horarios = horarios_em(texto)
    for url in re.findall(r"https?://[^\s\"'<>)]+|(?:wa\.me|instagram\.com|facebook\.com)/[^\s\"'<>)]+", texto or ""):
        classificar_link(url if "://" in url else "https://" + url, a)
    return a


def _decodificar_cfemail(hexa: str) -> str:
    try:
        chave = int(hexa[:2], 16)
        return "".join(chr(int(hexa[i:i + 2], 16) ^ chave) for i in range(2, len(hexa), 2))
    except ValueError:
        return ""


def _jsonld(arvore: HTMLParser) -> list[dict]:
    saida = []

    def visitar(obj):
        if isinstance(obj, list):
            for o in obj:
                visitar(o)
        elif isinstance(obj, dict):
            tipo = obj.get("@type")
            tipos = tipo if isinstance(tipo, list) else [tipo]
            if e_organizacao(tipos):
                saida.append(obj)
            for chave in ("@graph", "publisher", "provider", "seller", "brand", "author", "mainEntity"):
                if chave in obj:
                    visitar(obj[chave])

    for no in arvore.css('script[type="application/ld+json"]'):
        try:
            visitar(json.loads(no.text(deep=True) or "null"))
        except (json.JSONDecodeError, TypeError):
            continue
    return saida


def texto_visivel(arvore: HTMLParser) -> str:
    corpo = arvore.body or arvore.root
    if corpo is None:
        return ""
    for no in corpo.css("script, style, noscript, svg, template"):
        no.decompose()
    return corpo.text(separator="\n", strip=True)


def de_html(conteudo: str, url_base: str) -> tuple[Achados, dict]:
    """Extrai contatos de uma página. Retorna (achados, metadados da página)."""
    arvore = HTMLParser(conteudo)
    a = Achados()
    meta = {"titulo": "", "site_name": "", "descricao": "", "links_internos": []}

    t = arvore.css_first("title")
    meta["titulo"] = html.unescape(" ".join(t.text().split())) if t else ""
    for no in arvore.css("meta"):
        prop = (no.attributes.get("property") or no.attributes.get("name") or "").lower()
        conteudo = html.unescape(no.attributes.get("content") or "")
        if prop == "og:site_name":
            meta["site_name"] = conteudo.strip()
        elif prop in ("description", "og:description") and not meta["descricao"]:
            meta["descricao"] = conteudo.strip()

    a.jsonld = _jsonld(arvore)
    for no in arvore.css("[data-cfemail]"):
        a.emails += emails_em(_decodificar_cfemail(no.attributes.get("data-cfemail") or ""))

    dom = dominio(url_base)
    for no in arvore.css("a[href]"):
        href = (no.attributes.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:")):
            continue
        absoluto = urljoin(url_base, href)
        classificar_link(absoluto, a)
        if absoluto.startswith("http") and dominio(absoluto) == dom:
            meta["links_internos"].append((absoluto.split("#")[0], " ".join(no.text().split())[:80]))

    texto = texto_visivel(arvore)
    meta["texto"] = texto
    do_texto = de_texto(texto)
    a.juntar(do_texto)

    for org in a.jsonld:
        for chave in ("telephone", "faxNumber"):
            for v in (org.get(chave) if isinstance(org.get(chave), list) else [org.get(chave)]):
                if isinstance(v, str):
                    f = fone_de_digitos(v) or (telefones_em(v) or [None])[0]
                    if f and chave == "telephone":
                        a.telefones.insert(0, f)
        if isinstance(org.get("email"), str):
            a.emails = emails_em(org["email"].replace("mailto:", "")) + a.emails
        for s in org.get("sameAs") or []:
            if isinstance(s, str):
                classificar_link(s, a)
        for chave in ("taxID", "vatID", "identifier"):
            if isinstance(org.get(chave), str):
                a.cnpjs = cnpjlib.encontrar(org[chave]) + a.cnpjs
        if h := horario_jsonld(org):
            a.horarios.insert(0, h)  # declarado em dados estruturados: mais confiável que o texto
        if av := avaliacao_jsonld(org):
            a.avaliacoes.append(av)

    for nome in a.__dataclass_fields__:
        if nome != "jsonld":
            setattr(a, nome, unicos(getattr(a, nome)))
    return a, meta


def endereco_jsonld(org: dict) -> dict | None:
    end = org.get("address")
    if isinstance(end, list):
        end = end[0] if end else None
    if isinstance(end, str):
        return {"endereco": end}
    if not isinstance(end, dict):
        return None
    def s(v):
        return html.unescape(v).strip() if isinstance(v, str) else ""

    cep = re.sub(r"\D", "", s(end.get("postalCode")))
    return {
        "endereco": s(end.get("streetAddress")),
        "bairro": "",
        "cidade": s(end.get("addressLocality")),
        "uf": sigla_uf(s(end.get("addressRegion"))),
        "cep": f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else "",
    }
