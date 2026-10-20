"""Leitura e interpretação da lista de empresas.

Formatos aceitos (um item por linha em .txt; ou planilha .csv/.xlsx com cabeçalho):
    @perfil_instagram
    https://www.instagram.com/perfil/
    www.empresa.com.br
    12.345.678/0001-90
    Nome da Empresa
    Nome da Empresa | Cidade/UF | @perfil | site.com.br     (pistas extras separadas por "|" ou ";")
"""

import csv
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from empresas import cnpj as cnpjlib
from empresas.util import UFS

_RE_DOMINIO = re.compile(r"^(https?://)?([\w-]+\.)+[a-z]{2,}(:\d+)?(/\S*)?$", re.I)
_RE_IG = re.compile(r"instagram\.com/([A-Za-z0-9._]+)", re.I)
_RE_HANDLE = re.compile(r"^@([A-Za-z0-9._]{1,30})$")
_RE_CIDADE_UF = re.compile(r"^(.*?)[\s/,-]+([A-Za-z]{2})$")


@dataclass
class Entrada:
    linha: int
    original: str
    nome: str = ""
    instagram: str = ""   # só o @usuário, sem @
    site: str = ""
    cnpj: str = ""
    cidade: str = ""
    uf: str = ""
    dicas: list[str] = field(default_factory=list)

    @property
    def tipo(self) -> str:
        for t in ("cnpj", "instagram", "site", "nome"):
            if getattr(self, t):
                return t
        return "desconhecido"

    def dict(self):
        d = asdict(self)
        d["tipo"] = self.tipo
        return d


def _url_site(texto: str) -> str:
    t = texto.strip().rstrip("/")
    return t if t.lower().startswith("http") else "https://" + t


def _classificar_parte(parte: str, e: Entrada, primeira: bool):
    p = parte.strip().strip("\"'")
    if not p:
        return
    if m := _RE_HANDLE.match(p):
        e.instagram = e.instagram or m.group(1).lower().rstrip(".")
    elif m := _RE_IG.search(p):
        e.instagram = e.instagram or m.group(1).lower().rstrip(".")
    elif cnpjlib.valido(p) or (len(cnpjlib.limpar(p)) == 14 and re.fullmatch(r"[\d./\s-]+", p)):
        e.cnpj = e.cnpj or cnpjlib.limpar(p)
    elif " " not in p and _RE_DOMINIO.match(p) and "@" not in p:
        e.site = e.site or _url_site(p)
    elif not primeira and (m := _RE_CIDADE_UF.match(p)) and m.group(2).upper() in UFS:
        e.cidade, e.uf = e.cidade or m.group(1).strip(), e.uf or m.group(2).upper()
    elif not primeira and p.upper() in UFS:
        e.uf = e.uf or p.upper()
    elif primeira or not e.nome and not any((e.instagram, e.site, e.cnpj)):
        e.nome = e.nome or p
    elif not primeira and not e.cidade and len(p.split()) <= 4 and not any(ch.isdigit() for ch in p):
        e.cidade = p  # pista curta sem número: provavelmente a cidade
    else:
        e.dicas.append(p)


def de_linha(texto: str, linha: int) -> Entrada | None:
    t = texto.strip()
    if not t or t.startswith("#"):
        return None
    t = re.sub(r"^\s*(?:[-*•]|\d{1,4}[.)])\s+", "", t)  # marcadores de lista
    e = Entrada(linha=linha, original=t)
    for i, parte in enumerate(re.split(r"\s*[|;\t]\s*", t)):
        _classificar_parte(parte, e, primeira=(i == 0))
    return e


_COLUNAS = {
    "nome": ("nome", "empresa", "nome_fantasia", "nome fantasia", "nome comercial", "razao_social", "razão social", "razao social"),
    "instagram": ("instagram", "ig", "perfil", "@"),
    "site": ("site", "website", "url", "dominio", "domínio"),
    "cnpj": ("cnpj",),
    "cidade": ("cidade", "municipio", "município"),
    "uf": ("uf", "estado"),
}


def _de_tabela(linhas: list[list[str]]) -> list[Entrada]:
    cab = [str(c or "").strip().lower() for c in linhas[0]]
    mapa = {}
    for campo, nomes in _COLUNAS.items():
        for i, c in enumerate(cab):
            if c in nomes and campo not in mapa:
                mapa[campo] = i
    if not mapa:  # sem cabeçalho reconhecido: trata a primeira coluna como texto livre
        return [e for n, l in enumerate(linhas, 1) if l and (e := de_linha(" | ".join(str(x) for x in l if x), n))]
    saida = []
    for n, l in enumerate(linhas[1:], 2):
        valores = {k: str(l[i]).strip() if i < len(l) and l[i] is not None else "" for k, i in mapa.items()}
        partes = [valores.get("nome", "")] + [valores.get(k, "") for k in ("instagram", "site", "cnpj")]
        if valores.get("instagram") and not valores["instagram"].startswith("@") and "instagram" not in valores["instagram"]:
            partes[1] = "@" + valores["instagram"]
        local = "/".join(x for x in (valores.get("cidade"), valores.get("uf")) if x)
        e = de_linha(" | ".join([p for p in partes if p] + ([local] if local else [])), n)
        if e:
            saida.append(e)
    return saida


def ler(caminho: Path) -> list[Entrada]:
    sufixo = caminho.suffix.lower()
    if sufixo == ".xlsx":
        from openpyxl import load_workbook
        ws = load_workbook(caminho, read_only=True, data_only=True).active
        return _de_tabela([list(r) for r in ws.iter_rows(values_only=True)])
    texto = caminho.read_text(encoding="utf-8-sig")
    if sufixo == ".csv":
        dialeto = csv.Sniffer().sniff(texto[:2000], delimiters=",;\t") if texto.strip() else csv.excel
        return _de_tabela(list(csv.reader(texto.splitlines(), dialeto)))
    return [e for n, l in enumerate(texto.splitlines(), 1) if (e := de_linha(l, n))]
