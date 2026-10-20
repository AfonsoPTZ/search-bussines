"""Exportação da base de empresas (com os filtros aplicados na tela) em CSV (';', Excel BR) e XLSX.

Usa os valores de exibição da ferramenta de empresas: não confirmados levam o sufixo "(não confirmado)" e, no XLSX,
célula laranja. Segmento inferido aparece separado do segmento confirmado pelo perfil vinculado.
"""

import csv
import io
import json

from plataforma import consultas, db

COLUNAS = [
    ("id", "ID"), ("nome_comercial", "Nome"), ("segmentos_perfil", "Segmentos (perfil do Instagram)"),
    ("segmentos_inferidos", "Segmentos inferidos (não confirmados)"), ("status", "Status"),
    ("confianca", "Confiança"), ("cnpj", "CNPJ"), ("razao_social", "Razão social"), ("situacao_cadastral", "Situação cadastral"),
    ("atividade_principal", "Atividade principal (CNAE)"),
    ("cidade", "Cidade"), ("uf", "UF"), ("endereco_completo", "Endereço completo"), ("telefones", "Telefones"),
    ("whatsapp", "WhatsApp"), ("emails", "E-mails"), ("site", "Site"), ("instagram", "Instagram"),
    ("perfis", "Perfis vinculados"), ("nao_confirmados", "Campos não confirmados"), ("nao_encontrados", "Não encontrados"),
    ("divergencias", "Divergências"), ("ultima_pesquisa", "Última pesquisa"), ("n_pesquisas", "Pesquisas"),
    ("execucao", "Execução exibida"), ("fontes_principais", "Fontes principais"),
]
_DA_PLANILHA = {"nome_comercial", "atividade_principal", "cnpj", "razao_social", "situacao_cadastral", "cidade", "uf",
                "endereco_completo", "telefones", "whatsapp", "emails", "site", "instagram", "nao_confirmados",
                "nao_encontrados", "divergencias", "fontes_principais"}


def texto_seguro(v):
    """Valor vindo da web nunca vira fórmula no Excel ("=HYPERLINK(...)"); telefones como +55 continuam iguais."""
    if isinstance(v, str) and v[:1] in ("=", "@", "\t", "\r") or isinstance(v, str) and v[:1] in "+-" and v[1:2] and not v[1:2].isdigit() and v[1:2] != " ":
        return "'" + v
    return v


def linhas(filtros: dict) -> list[dict]:
    from empresas.exportar import linha_planilha
    from prospeccao import categorias as cats

    con = db.conexao()
    nomes = {c.codigo: f"{c.codigo} {c.nome}" for c in cats.CATEGORIAS}
    saida = []
    for eid in consultas.ids_empresas(filtros, limite=100_000):
        e = con.execute("SELECT e.*, p.registro, p.execucao_id FROM empresas e LEFT JOIN pesquisas p ON p.id=e.pesquisa_atual "
                        "WHERE e.id=?", (eid,)).fetchone()
        if not e or not e["registro"]:
            continue
        l = linha_planilha(json.loads(e["registro"]))
        seg_p = consultas._segs(e["segmentos_perfil"])
        seg_i = [s for s in consultas._segs(e["segmentos_inferidos"]) if s not in seg_p]
        perfis = [f"@{r[0]}" + ("" if r[1] == "confirmado" else " (sugerido)") for r in con.execute(
            "SELECT usuario, estado FROM vinculos WHERE empresa_id=? AND estado<>'rejeitado' ORDER BY estado, usuario", (eid,))]
        d = {k: l.get(k, "") for k in _DA_PLANILHA}
        d.update(id=eid, segmentos_perfil=", ".join(nomes.get(s, s) for s in seg_p),
                 segmentos_inferidos=", ".join(nomes.get(s, s) for s in seg_i), status=e["status"], confianca=e["confianca"],
                 perfis=", ".join(perfis), ultima_pesquisa=(e["ultima_pesquisa"] or "")[:10], n_pesquisas=e["n_pesquisas"],
                 execucao=e["execucao_id"], _nao=l["_nao_confirmados"])
        saida.append(d)
    return saida


def csv_bytes(filtros: dict) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow([t for _, t in COLUNAS])
    for l in linhas(filtros):
        w.writerow([texto_seguro(l.get(k, "")) for k, _ in COLUNAS])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def xlsx_bytes(filtros: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    from empresas.exportar import _COR_NAO_CONFIRMADO, _formatar_aba

    wb = Workbook()
    ws = wb.active
    ws.title = "Empresas"
    ws.append([t for _, t in COLUNAS])
    idx = {k: i for i, (k, _) in enumerate(COLUNAS, 1)}
    laranja = PatternFill("solid", fgColor=_COR_NAO_CONFIRMADO)
    for n, l in enumerate(linhas(filtros), 2):
        ws.append([l.get(k, "") for k, _ in COLUNAS])
        for cel in ws[n]:
            if cel.data_type == "f":  # texto que começa com "=" é texto, não fórmula
                cel.data_type = "s"
        for c in l["_nao"] | ({"segmentos_inferidos"} if l["segmentos_inferidos"] else set()):
            if c in idx:
                ws.cell(n, idx[c]).fill = laranja
                ws.cell(n, idx[c]).font = Font(italic=True)
    _formatar_aba(ws)
    leg = wb.create_sheet("Legenda")
    for linha in (("Termo", "Significado"),
                  ("(não confirmado) / célula laranja", "Valor encontrado sem prova de que é desta empresa; confira a fonte."),
                  ("Segmentos (perfil do Instagram)", "Segmentos A–M do perfil vinculado e identificado pela análise de seguidores."),
                  ("Segmentos inferidos", "Regras A–M aplicadas ao nome/categoria/atividade da empresa. Não confirmado."),
                  ("Perfis vinculados", "(sugerido) = vínculo ainda não confirmado."),
                  ("Campos vazios", "Nada encontrado com fonte. Nada é inventado.")):
        leg.append(list(linha))
    _formatar_aba(leg, {1: 36, 2: 100})
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
