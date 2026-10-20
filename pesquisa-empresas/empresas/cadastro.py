"""Consulta de CNPJ em APIs públicas gratuitas (dados abertos da Receita Federal), com contingência.

Ordem: OpenCNPJ -> BrasilAPI -> minhareceita.org -> CNPJá open (5/min).
Todas retornam o mesmo dado de origem (Receita Federal); a diferença é disponibilidade e campos.
"""

import re

import httpx

from empresas import cnpj as cnpjlib
from empresas import config
from empresas.extrair import fone_de_digitos
from empresas.util import cache, ritmo
from empresas.web import cliente


def _endereco(tipo, logradouro, numero, complemento):
    rua = " ".join(x for x in (tipo, logradouro) if x).strip()
    partes = [rua] + [x for x in (numero, complemento) if x]
    return ", ".join(p for p in partes if p).title() if rua else ""


def _de_opencnpj(d: dict) -> dict:
    principal = next((c for c in d.get("cnaes", []) if c.get("is_principal")), {})
    return {
        "cnpj": d["cnpj"],
        "razao_social": d.get("razao_social") or "",
        "nome_fantasia": d.get("nome_fantasia") or "",
        "situacao": (d.get("situacao_cadastral") or "").upper(),
        "data_situacao": d.get("data_situacao_cadastral") or "",
        "matriz_filial": d.get("matriz_filial") or "",
        "cnae": f"{d.get('cnae_principal', '')} - {principal.get('descricao', '')}".strip(" -"),
        "natureza_juridica": d.get("natureza_juridica") or "",
        "porte": d.get("porte_empresa") or "",
        "mei": (d.get("opcao_mei") or "").upper() == "S",
        "endereco": _endereco(d.get("tipo_logradouro"), d.get("logradouro"), d.get("numero"), d.get("complemento")),
        "bairro": (d.get("bairro") or "").title(),
        "municipio": (d.get("municipio") or "").title(),
        "uf": d.get("uf") or "",
        "cep": d.get("cep") or "",
        "telefones": [f for t in d.get("telefones", []) if not t.get("is_fax")
                      if (f := fone_de_digitos(f"{t.get('ddd', '')}{t.get('numero', '')}"))],
        "email": (d.get("email") or "").lower(),
    }


def _de_brasilapi(d: dict) -> dict:
    """Formato usado por BrasilAPI e minhareceita.org."""
    return {
        "cnpj": d["cnpj"],
        "razao_social": d.get("razao_social") or "",
        "nome_fantasia": d.get("nome_fantasia") or "",
        "situacao": (d.get("descricao_situacao_cadastral") or "").upper(),
        "data_situacao": d.get("data_situacao_cadastral") or "",
        "matriz_filial": (d.get("descricao_identificador_matriz_filial") or "").title(),
        "cnae": f"{d.get('cnae_fiscal', '')} - {d.get('cnae_fiscal_descricao', '')}".strip(" -"),
        "natureza_juridica": d.get("natureza_juridica") or "",
        "porte": d.get("porte") or "",
        "mei": bool(d.get("opcao_pelo_mei")),
        "endereco": _endereco(d.get("descricao_tipo_de_logradouro"), d.get("logradouro"), d.get("numero"), d.get("complemento")),
        "bairro": (d.get("bairro") or "").title(),
        "municipio": (d.get("municipio") or "").title(),
        "uf": d.get("uf") or "",
        "cep": str(d.get("cep") or ""),
        "telefones": [f for k in ("ddd_telefone_1", "ddd_telefone_2") if (f := fone_de_digitos(d.get(k) or ""))],
        "email": (d.get("email") or "").lower(),
    }


def _de_cnpja(d: dict) -> dict:
    end = d.get("address") or {}
    emp = d.get("company") or {}
    return {
        "cnpj": d["taxId"],
        "razao_social": emp.get("name") or "",
        "nome_fantasia": d.get("alias") or "",
        "situacao": ((d.get("status") or {}).get("text") or "").upper(),
        "data_situacao": d.get("statusDate") or "",
        "matriz_filial": "Matriz" if d.get("head") else "Filial",
        "cnae": f"{(d.get('mainActivity') or {}).get('id', '')} - {(d.get('mainActivity') or {}).get('text', '')}".strip(" -"),
        "natureza_juridica": (emp.get("nature") or {}).get("text") or "",
        "porte": (emp.get("size") or {}).get("text") or "",
        "mei": bool((emp.get("simei") or {}).get("optant")),
        "endereco": _endereco("", end.get("street"), end.get("number"), end.get("details")),
        "bairro": end.get("district") or "",
        "municipio": end.get("city") or "",
        "uf": end.get("state") or "",
        "cep": end.get("zip") or "",
        "telefones": [f for p in d.get("phones", []) if (f := fone_de_digitos(f"{p.get('area', '')}{p.get('number', '')}"))],
        "email": next((e.get("address", "") for e in d.get("emails", [])), "").lower(),
    }


FONTES = [
    ("opencnpj", "https://api.opencnpj.org/{c}", _de_opencnpj),
    ("brasilapi", "https://brasilapi.com.br/api/cnpj/v1/{c}", _de_brasilapi),
    ("minhareceita", "https://minhareceita.org/{c}", _de_brasilapi),
    ("cnpja", "https://open.cnpja.com/office/{c}", _de_cnpja),
]


class CnpjInexistente(Exception):
    pass


def consultar_cep(cep: str) -> dict | None:
    """Logradouro, bairro, cidade e UF de um CEP (BrasilAPI, com ViaCEP de contingência). None se não existir."""
    c = re.sub(r"\D", "", cep or "")
    if len(c) != 8:
        return None
    chave = f"cep:{c}"
    em_cache = cache().obter(chave, config.TTL_CADASTRO)
    if em_cache is not None:
        return em_cache or None
    fontes = [
        ("brasilapi", f"https://brasilapi.com.br/api/cep/v2/{c}",
         lambda d: (d.get("street"), d.get("neighborhood"), d.get("city"), d.get("state"))),
        ("viacep", f"https://viacep.com.br/ws/{c}/json/",
         lambda d: None if d.get("erro") else (d.get("logradouro"), d.get("bairro"), d.get("localidade"), d.get("uf"))),
    ]
    nao_existe = 0
    for nome, url, ler in fontes:
        ritmo.esperar(nome, config.INTERVALO.get(nome, 0.6))
        try:
            r = cliente().get(url, timeout=15)
        except httpx.HTTPError:
            continue
        if r.status_code in (400, 404):
            nao_existe += 1
            continue
        if r.status_code != 200:
            continue
        try:
            campos = ler(r.json())
        except ValueError:
            continue
        if campos is None:
            nao_existe += 1
            continue
        rua, bairro, cidade, uf = (x or "" for x in campos)
        dados = {"cep": f"{c[:5]}-{c[5:]}", "logradouro": rua, "bairro": bairro, "cidade": cidade, "uf": uf,
                 "fonte_url": url}
        cache().gravar(chave, dados)
        return dados
    if nao_existe:
        cache().gravar(chave, {})  # CEP inexistente: não consultar de novo
    return None


def consultar(valor: str) -> dict | None:
    """Dados cadastrais normalizados, ou None se nenhuma fonte respondeu.

    Lança CnpjInexistente se o CNPJ for inválido ou se as fontes disserem que ele não existe.
    """
    c = cnpjlib.limpar(valor)
    if not cnpjlib.valido(c):
        raise CnpjInexistente(f"CNPJ inválido: {valor}")

    chave = f"cnpj:{c}"
    em_cache = cache().obter(chave, config.TTL_CADASTRO)
    if em_cache is not None:
        return em_cache

    nao_existe = 0
    for nome, modelo, normalizar in FONTES:
        url = modelo.format(c=c)
        for tentativa in range(2):
            ritmo.esperar(nome, config.INTERVALO[nome])
            try:
                r = cliente().get(url, timeout=20)
            except httpx.HTTPError:
                break
            if r.status_code == 429 and tentativa == 0:
                ritmo.esperar(nome, 15)
                continue
            if r.status_code == 404:
                nao_existe += 1
            if r.status_code != 200:
                break
            try:
                dados = normalizar(r.json())
            except (ValueError, KeyError, TypeError):
                break
            dados["fonte"] = nome
            dados["fonte_url"] = url
            dados["cnpj"] = cnpjlib.limpar(dados["cnpj"])
            cache().gravar(chave, dados)
            return dados
    if nao_existe >= 2:
        raise CnpjInexistente(f"CNPJ não encontrado nas bases públicas: {cnpjlib.formatar(c)}")
    return None
