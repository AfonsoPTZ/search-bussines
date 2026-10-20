"""Consultas da interface: listas com filtros (aplicados no SQL), detalhes e indicadores.

Os filtros chegam como dicionário de textos (vindos da URL). Valores múltiplos vêm separados por vírgula.
Todo nome de coluna usado em ORDER BY vem de uma lista fixa; valores sempre como parâmetros.
"""

import json
from datetime import datetime, timedelta

from plataforma import config, db
from plataforma import normalizar as nz

POR_PAGINA = 50
STATUS_EMPRESA = {
    "identificada": "CNPJ confirmado", "provavel": "CNPJ provável (não confirmado)", "parcial": "Sem CNPJ; contatos/site",
    "ambigua": "Ambígua (lote antigo)", "nao_encontrada": "Nada encontrado", "erro": "Erro técnico",
}
ESTADOS_EXECUCAO = {
    "criada": "Criada (não iniciada)", "em_andamento": "Em andamento", "aguardando": "Aguardando o Instagram",
    "concluida": "Concluída", "concluida_parcial": "Concluída parcialmente", "concluida_com_falhas": "Concluída com falhas",
    "interrompida": "Interrompida", "pausada": "Pausada", "parada": "Parada sem finalizar", "precisa_acao": "Precisa de você",
    "falhou": "Falhou",
}


def _lista(v) -> list[str]:
    if not v:
        return []
    return [x.strip() for x in str(v).split(",") if x.strip()]


def _int(v, padrao: int, minimo: int = 1, maximo: int = 10_000) -> int:
    try:
        return max(minimo, min(maximo, int(v)))
    except (TypeError, ValueError):
        return padrao


def _em(campo: str, valores: list, params: list) -> str:
    params.extend(valores)
    return f"{campo} IN ({','.join('?' * len(valores))})"


def _texto(campo: str, q: str, params: list) -> list[str]:
    conds = []
    for termo in nz.texto(q).split():
        conds.append(f"{campo} LIKE ?")
        params.append(f"%{termo}%")
    return conds


def segmentos() -> list[dict]:
    from prospeccao import categorias as cats
    return [{"codigo": c.codigo, "nome": c.nome, "descricao": c.descricao} for c in cats.CATEGORIAS]


def _segs(v: str | None) -> list[str]:
    return [s for s in (v or "").strip(",").split(",") if s]


# ----------------------------------------------------------------------------------------- empresas

_ORDEM_EMPRESAS = {
    "nome": "e.nome COLLATE NOCASE ASC", "-nome": "e.nome COLLATE NOCASE DESC",
    "-ultima_pesquisa": "e.ultima_pesquisa DESC", "ultima_pesquisa": "e.ultima_pesquisa ASC",
    "-completude": "e.completude DESC, e.n_nao_confirmados ASC", "completude": "e.completude ASC",
    "cidade": "e.uf, e.cidade_chave, e.nome COLLATE NOCASE", "status": "e.status, e.nome COLLATE NOCASE",
}


def _filtro_empresas(f: dict) -> tuple[str, list]:
    params: list = []
    w = [] if f.get("ocultas") == "1" else ["e.visivel=1"]
    if f.get("q"):
        w += _texto("e.busca", f["q"], params)
    if ufs := [u.upper() for u in _lista(f.get("uf"))]:
        w.append(_em("e.uf", ufs, params))
    if cidades := [nz.texto(c) for c in _lista(f.get("cidade"))]:
        w.append(_em("e.cidade_chave", cidades, params))
    if st := _lista(f.get("status")):
        w.append(_em("e.status", st, params))
    if cf := _lista(f.get("confianca")):
        w.append(_em("e.confianca", cf, params))
    if segs := _lista(f.get("segmento")):
        origem = f.get("origem_segmento") or "qualquer"
        conds = []
        for s in segs:
            if origem in ("qualquer", "perfil"):
                conds.append("e.segmentos_perfil LIKE ?")
                params.append(f"%,{s},%")
            if origem in ("qualquer", "inferido"):
                conds.append("e.segmentos_inferidos LIKE ?")
                params.append(f"%,{s},%")
        w.append("(" + " OR ".join(conds) + ")")
    elif f.get("origem_segmento") == "sem":
        w.append("e.segmentos_perfil='' AND e.segmentos_inferidos=''")
    ig = f.get("instagram")
    if ig == "com":
        w.append("(e.instagram<>'' OR EXISTS(SELECT 1 FROM vinculos v WHERE v.empresa_id=e.id AND v.estado<>'rejeitado'))")
    elif ig == "sem":
        w.append("e.instagram='' AND NOT EXISTS(SELECT 1 FROM vinculos v WHERE v.empresa_id=e.id AND v.estado<>'rejeitado')")
    elif ig == "vinculado":
        w.append("EXISTS(SELECT 1 FROM vinculos v JOIN perfis p ON p.usuario=v.usuario WHERE v.empresa_id=e.id AND v.estado='confirmado')")
    elif ig == "sugerido":
        w.append("EXISTS(SELECT 1 FROM vinculos v WHERE v.empresa_id=e.id AND v.estado='sugerido')")
    contato = f.get("contato")
    if contato == "com":
        w.append("(e.telefone<>'' OR e.whatsapp<>'' OR e.email<>'')")
    elif contato == "sem":
        w.append("e.telefone='' AND e.whatsapp='' AND e.email=''")
    elif contato == "whatsapp":
        w.append("e.whatsapp<>''")
    for p in _lista(f.get("pendencia")):
        if p == "revisar":
            w.append("e.precisa_revisao=1 AND e.revisada=0")
        elif p == "revisada":
            w.append("e.revisada=1")
        elif p == "desatualizada":
            w.append("e.ultima_pesquisa < ?")
            params.append((datetime.now() - timedelta(days=config.DIAS_DESATUALIZADA)).isoformat(timespec="seconds"))
        elif p == "nao_confirmados":
            w.append("e.n_nao_confirmados > 0")
        elif p == "divergencia":
            w.append("e.divergencias > 0")
        elif p == "duplicidade":
            w.append("EXISTS(SELECT 1 FROM duplicidades d WHERE (d.a=e.id OR d.b=e.id) AND d.estado='pendente')")
        elif p == "erro":
            w.append("e.status='erro'")
        elif p == "sem_cnpj":
            w.append("e.cnpj_confirmado=0")
    if f.get("completude_min"):
        w.append("e.completude >= ?")
        params.append(_int(f["completude_min"], 0, 0, 20))
    if f.get("desde"):
        w.append("e.ultima_pesquisa >= ?")
        params.append(f["desde"][:10])
    if f.get("ate"):
        w.append("e.ultima_pesquisa < ?")
        params.append((datetime.fromisoformat(f["ate"][:10]) + timedelta(days=1)).date().isoformat())
    if ex := _lista(f.get("execucao")):
        w.append("EXISTS(SELECT 1 FROM pesquisas p WHERE p.empresa_id=e.id AND " + _em("p.execucao_id", ex, params) + ")")
    origem = f.get("origem")
    if origem == "instagram":
        w.append("EXISTS(SELECT 1 FROM pesquisas p JOIN execucoes x ON x.id=p.execucao_id WHERE p.empresa_id=e.id "
                 "AND x.origem_execucao LIKE 'ig:%')")
    elif origem == "lista":
        w.append("NOT EXISTS(SELECT 1 FROM pesquisas p JOIN execucoes x ON x.id=p.execucao_id WHERE p.empresa_id=e.id "
                 "AND x.origem_execucao LIKE 'ig:%')")
    return (" WHERE " + " AND ".join(w)) if w else "", params


def _item_empresa(r) -> dict:
    d = dict(r)
    d.pop("busca", None)
    d["segmentos_perfil"] = _segs(d["segmentos_perfil"])
    d["segmentos_inferidos"] = [s for s in _segs(d["segmentos_inferidos"]) if s not in d["segmentos_perfil"]]
    return d


def listar_empresas(f: dict) -> dict:
    where, params = _filtro_empresas(f)
    con = db.conexao()
    total = con.execute(f"SELECT COUNT(*) FROM empresas e{where}", params).fetchone()[0]
    por_pagina = _int(f.get("por_pagina"), POR_PAGINA, 1, 500)
    pagina = _int(f.get("pagina"), 1, 1, 100_000)
    ordem = _ORDEM_EMPRESAS.get(f.get("ordenar") or "", _ORDEM_EMPRESAS["nome"])
    linhas = con.execute(
        f"""SELECT e.*, (SELECT COUNT(*) FROM vinculos v WHERE v.empresa_id=e.id AND v.estado='confirmado') AS perfis_confirmados,
            (SELECT COUNT(*) FROM vinculos v WHERE v.empresa_id=e.id AND v.estado='sugerido') AS perfis_sugeridos,
            (SELECT COUNT(*) FROM duplicidades d WHERE (d.a=e.id OR d.b=e.id) AND d.estado='pendente') AS duplicidades
            FROM empresas e{where} ORDER BY {ordem}, e.id LIMIT ? OFFSET ?""",
        params + [por_pagina, (pagina - 1) * por_pagina]).fetchall()
    return {"itens": [_item_empresa(r) for r in linhas], "total": total, "pagina": pagina, "por_pagina": por_pagina,
            "paginas": max(1, -(-total // por_pagina))}


def ids_empresas(f: dict, limite: int = 5000) -> list[int]:
    where, params = _filtro_empresas(f)
    return [r[0] for r in db.conexao().execute(f"SELECT e.id FROM empresas e{where} ORDER BY e.id LIMIT ?", params + [limite])]


def opcoes_empresas() -> dict:
    con = db.conexao()
    q = lambda sql: [dict(r) for r in con.execute(sql)]
    seg_cont = {"perfil": {}, "inferido": {}}
    for r in con.execute("SELECT segmentos_perfil, segmentos_inferidos FROM empresas WHERE visivel=1"):
        for s in _segs(r[0]):
            seg_cont["perfil"][s] = seg_cont["perfil"].get(s, 0) + 1
        for s in _segs(r[1]):
            if s not in _segs(r[0]):
                seg_cont["inferido"][s] = seg_cont["inferido"].get(s, 0) + 1
    return {
        "ufs": q("SELECT uf AS valor, COUNT(*) AS n FROM empresas WHERE visivel=1 AND uf<>'' GROUP BY uf ORDER BY n DESC, uf"),
        "cidades": q("SELECT MAX(cidade) AS valor, uf, COUNT(*) AS n FROM empresas WHERE visivel=1 AND cidade_chave<>'' "
                     "GROUP BY cidade_chave, uf ORDER BY n DESC, valor LIMIT 300"),
        "status": [dict(r) | {"rotulo": STATUS_EMPRESA.get(r["valor"], r["valor"])} for r in con.execute(
            "SELECT status AS valor, COUNT(*) AS n FROM empresas WHERE visivel=1 GROUP BY status ORDER BY n DESC")],
        "segmentos": [s | {"perfil": seg_cont["perfil"].get(s["codigo"], 0), "inferido": seg_cont["inferido"].get(s["codigo"], 0)}
                      for s in segmentos()],
        "execucoes": q("SELECT id AS valor, nome, referencia FROM execucoes WHERE tipo='empresas' ORDER BY id DESC"),
    }


def _estado_campo(itens: list[dict], encontrado: bool) -> str:
    if not itens:
        return "nao_encontrado" if not encontrado else "vazio"
    conf = [i.get("confirmado", True) for i in itens]
    if all(conf):
        return "confirmado"
    if conf[0] or any(conf):
        return "parcial"
    return "nao_confirmado"


def _correcoes_da_linha(pasta: str, linha: int) -> list[dict]:
    from pathlib import Path
    saida = []
    arq = Path(pasta) / "correcoes.jsonl"
    if arq.exists():
        for l in arq.read_text(encoding="utf-8").splitlines():
            try:
                c = json.loads(l)
            except ValueError:
                continue
            if c.get("linha") == linha:
                saida.append({k: c.get(k) for k in ("campo", "valor", "fonte", "nota", "em", "confirmar", "remover",
                                                    "nao_confirmado", "substituir")})
    return saida


def detalhe_empresa(eid: int) -> dict | None:
    from empresas.exportar import NOMES_CAMPOS, _ordenar, linha_planilha
    from empresas.pesquisa import CAMPOS, CAMPOS_ESSENCIAIS

    con = db.conexao()
    e = con.execute("SELECT * FROM empresas WHERE id=?", (eid,)).fetchone()
    if not e:
        return None
    pesqs = con.execute("SELECT p.*, x.nome AS execucao_nome, x.pasta AS pasta, x.origem_execucao, "
                        "COALESCE(m.arquivada, 0) AS arquivada FROM pesquisas p JOIN execucoes x ON x.id=p.execucao_id "
                        "LEFT JOIN execucao_meta m ON m.execucao_id=p.execucao_id WHERE p.empresa_id=? "
                        "ORDER BY MAX(COALESCE(p.revisado_em,''), p.data) DESC", (eid,)).fetchall()
    atual = next((p for p in pesqs if p["id"] == e["pesquisa_atual"]), pesqs[0] if pesqs else None)
    campos = []
    reg = json.loads(atual["registro"]) if atual else {"campos": {}}
    linha = linha_planilha(reg) if atual else {}
    for c in CAMPOS:
        itens = _ordenar(c, reg["campos"].get(c, []))
        if not itens and c not in CAMPOS_ESSENCIAIS:
            continue
        vistos, valores = set(), []
        for i in itens:
            chave = (nz.texto(i["valor"]) or i["valor"], i.get("confirmado", True))
            if chave in vistos:
                continue
            vistos.add(chave)
            valores.append({"valor": i["valor"], "confirmado": i.get("confirmado", True), "origem": i["origem"],
                            "fonte": i.get("fonte", "")})
        campos.append({"campo": c, "rotulo": NOMES_CAMPOS.get(c, c), "valores": valores,
                       "estado": _estado_campo(itens, c not in (reg.get("nao_encontrados") or []))})
    vinculos = [dict(r) for r in con.execute(
        "SELECT v.*, p.nome, p.situacao, p.segmentos, p.confianca, p.seguidores, p.categoria_ig, p.bio, "
        "(p.usuario IS NOT NULL) AS analisado FROM vinculos v LEFT JOIN perfis p ON p.usuario=v.usuario "
        "WHERE v.empresa_id=? ORDER BY v.estado='confirmado' DESC, v.usuario", (eid,))]
    for v in vinculos:
        v["segmentos"] = _segs(v["segmentos"])
    dups = []
    for d in con.execute("SELECT * FROM duplicidades WHERE (a=? OR b=?) AND estado='pendente'", (eid, eid)):
        outro = d["b"] if d["a"] == eid else d["a"]
        o = con.execute("SELECT id, nome, cidade, uf, cnpj, status, n_pesquisas FROM empresas WHERE id=?", (outro,)).fetchone()
        if o:
            dups.append({"a": d["a"], "b": d["b"], "motivo": d["motivo"], "outra": dict(o)})
    item = _item_empresa(e)
    return {
        "empresa": item,
        "atual": {"id": atual["id"], "execucao_id": atual["execucao_id"], "execucao_nome": atual["execucao_nome"],
                  "entrada": atual["entrada"], "data": atual["data"], "revisado_em": atual["revisado_em"],
                  "status": atual["status"], "confianca": atual["confianca"]} if atual else None,
        "campos": campos,
        "endereco_completo": linha.get("endereco_completo", ""),
        "divergencias": reg.get("divergencias") or [], "observacoes": reg.get("observacoes") or [],
        "nao_encontrados": [NOMES_CAMPOS.get(c, c) for c in reg.get("nao_encontrados") or []],
        "candidatos_cnpj": [{k: c.get(k, "") for k in ("cnpj", "escolhido", "razao_social", "nome_fantasia", "cidade", "situacao",
                                                        "pontuacao", "motivos")} for c in (reg.get("candidatos_cnpj") or [])[:6]],
        "alternativas": reg.get("alternativas") or [],
        "consultas": len(reg.get("consultas") or []),
        "correcoes": _correcoes_da_linha(atual["pasta"], atual["linha"]) if atual else [],
        "historico": [{"id": p["id"], "execucao_id": p["execucao_id"], "execucao_nome": p["execucao_nome"], "linha": p["linha"],
                       "entrada": p["entrada"], "status": p["status"], "confianca": p["confianca"], "data": p["data"],
                       "revisado_em": p["revisado_em"], "cnpj": p["cnpj"], "cnpj_confirmado": p["cnpj_confirmado"],
                       "atual": p["id"] == (atual["id"] if atual else None), "arquivada": p["arquivada"],
                       "origem_execucao": p["origem_execucao"]} for p in pesqs],
        "perfis": vinculos, "duplicidades": dups,
        "segmentos": segmentos(),
    }


# ----------------------------------------------------------------------------------------- perfis

_ORDEM_PERFIS = {"usuario": "p.usuario", "-seguidores": "p.seguidores DESC", "-em": "p.em DESC",
                 "segmento": "p.segmentos, p.usuario"}


def listar_perfis(f: dict) -> dict:
    con = db.conexao()
    params: list = []
    ex = f.get("execucao")
    if ex:
        fonte = "perfil_execucao pe JOIN perfis p ON p.usuario=pe.usuario"
        col_sit, col_seg, col_conf = "pe.situacao", "pe.segmentos", "pe.confianca"
        w = ["pe.execucao_id=?"]
        params.append(ex)
    else:
        fonte = "perfis p"
        col_sit, col_seg, col_conf = "p.situacao", "p.segmentos", "p.confianca"
        w = ["EXISTS(SELECT 1 FROM perfil_execucao pe2 LEFT JOIN execucao_meta m ON m.execucao_id=pe2.execucao_id "
             "WHERE pe2.usuario=p.usuario AND COALESCE(m.arquivada,0)=0)"]
    if f.get("q"):
        w += _texto("p.busca", f["q"], params)
    if sit := _lista(f.get("situacao")):
        w.append(_em(col_sit, sit, params))
    if segs := _lista(f.get("segmento")):
        w.append("(" + " OR ".join(f"{col_seg} LIKE ?" for _ in segs) + ")")
        params += [f"%,{s},%" for s in segs]
    if cf := _lista(f.get("confianca")):
        w.append(_em(col_conf, cf, params))
    if tp := _lista(f.get("tipo_perfil")):
        w.append(_em("p.tipo_perfil", tp, params))
    emp = f.get("empresa")
    tem_vinc = "EXISTS(SELECT 1 FROM vinculos v WHERE v.usuario=p.usuario AND v.estado='confirmado')"
    if emp == "com":
        w.append(tem_vinc)
    elif emp == "sem":
        w.append("NOT " + tem_vinc)
    elif emp == "sugerido":
        w.append("EXISTS(SELECT 1 FROM vinculos v WHERE v.usuario=p.usuario AND v.estado='sugerido')")
    if f.get("revisado") == "sim":
        w.append("p.revisado=1")
    elif f.get("revisado") == "nao":
        w.append("p.revisado=0")
    where = " WHERE " + " AND ".join(w)
    total = con.execute(f"SELECT COUNT(*) FROM {fonte}{where}", params).fetchone()[0]
    por_pagina = _int(f.get("por_pagina"), POR_PAGINA, 1, 500)
    pagina = _int(f.get("pagina"), 1, 1, 100_000)
    ordem = _ORDEM_PERFIS.get(f.get("ordenar") or "", f"{col_sit}='identificado' DESC, {col_conf}, p.usuario")
    linhas = con.execute(
        f"""SELECT p.usuario, p.nome, p.categoria_ig, p.seguidores, p.tipo_perfil, p.estado_analise, p.cidade, p.revisado,
            p.conta_comercial, p.privado, p.bio, {col_sit} AS situacao, {col_seg} AS segmentos, {col_conf} AS confianca,
            (SELECT v.empresa_id FROM vinculos v WHERE v.usuario=p.usuario AND v.estado='confirmado' LIMIT 1) AS empresa_id,
            (SELECT e.nome FROM vinculos v JOIN empresas e ON e.id=v.empresa_id WHERE v.usuario=p.usuario AND v.estado='confirmado' LIMIT 1) AS empresa_nome,
            (SELECT COUNT(*) FROM vinculos v WHERE v.usuario=p.usuario AND v.estado='sugerido') AS sugeridos
            FROM {fonte}{where} ORDER BY {ordem} LIMIT ? OFFSET ?""",
        params + [por_pagina, (pagina - 1) * por_pagina]).fetchall()
    itens = []
    for r in linhas:
        d = dict(r)
        d["segmentos"] = _segs(d["segmentos"])
        d["bio"] = (d["bio"] or "")[:200]
        itens.append(d)
    return {"itens": itens, "total": total, "pagina": pagina, "por_pagina": por_pagina, "paginas": max(1, -(-total // por_pagina))}


def detalhe_perfil(usuario: str) -> dict | None:
    con = db.conexao()
    p = con.execute("SELECT * FROM perfis WHERE usuario=?", (usuario,)).fetchone()
    if not p:
        return None
    d = dict(p)
    d.pop("busca", None)
    d["segmentos"] = _segs(d["segmentos"])
    d["classificacao"] = json.loads(d["classificacao"] or "{}")
    d["perfil"] = json.loads(d["perfil"] or "{}")
    execs = [dict(r) | {"segmentos": _segs(r["segmentos"])} for r in con.execute(
        "SELECT pe.*, x.referencia, x.nome AS execucao_nome FROM perfil_execucao pe JOIN execucoes x ON x.id=pe.execucao_id "
        "WHERE pe.usuario=? ORDER BY pe.em DESC", (usuario,))]
    vinc = [dict(r) for r in con.execute(
        "SELECT v.*, e.nome AS empresa_nome, e.cidade, e.uf, e.status, e.cnpj FROM vinculos v JOIN empresas e ON e.id=v.empresa_id "
        "WHERE v.usuario=? ORDER BY v.estado='confirmado' DESC", (usuario,))]
    return {"perfil": d, "execucoes": execs, "vinculos": vinc, "segmentos": segmentos()}


# ----------------------------------------------------------------------------------------- execuções

def _execucao(r) -> dict:
    d = dict(r)
    for k in ("assinatura_estado", "assinatura_dados", "dados_lidos_em"):
        d.pop(k, None)
    d["resumo"] = json.loads(d["resumo"] or "{}")
    d["rotulo_estado"] = ESTADOS_EXECUCAO.get(d["estado"], d["estado"])
    if d["tipo"] == "instagram" and d["resumo"].get("dados"):
        # calculado na hora: muda quando empresas são pesquisadas/vinculadas, sem a análise mudar
        d["resumo"]["dados"]["sem_empresa"] = db.conexao().execute(
            "SELECT COUNT(*) FROM perfil_execucao pe WHERE pe.execucao_id=? AND pe.situacao='identificado' AND NOT EXISTS "
            "(SELECT 1 FROM vinculos v WHERE v.usuario=pe.usuario AND v.estado='confirmado')", (d["id"],)).fetchone()[0]
    return d


def listar_execucoes(f: dict) -> dict:
    con = db.conexao()
    params: list = []
    w = []
    if tipos := _lista(f.get("tipo")):
        w.append(_em("x.tipo", tipos, params))
    if est := _lista(f.get("estado")):
        w.append(_em("x.estado", est, params))
    if f.get("q"):
        w.append("(x.nome LIKE ? OR x.referencia LIKE ?)")
        params += [f"%{f['q']}%"] * 2
    if f.get("arquivadas") != "1":
        w.append("COALESCE(m.arquivada,0)=0")
    where = (" WHERE " + " AND ".join(w)) if w else ""
    fonte = "execucoes x LEFT JOIN execucao_meta m ON m.execucao_id=x.id"
    total = con.execute(f"SELECT COUNT(*) FROM {fonte}{where}", params).fetchone()[0]
    por_pagina = _int(f.get("por_pagina"), POR_PAGINA, 1, 200)
    pagina = _int(f.get("pagina"), 1, 1, 100_000)
    linhas = con.execute(f"SELECT x.*, COALESCE(m.arquivada,0) AS arquivada FROM {fonte}{where} "
                         f"ORDER BY x.em_andamento DESC, COALESCE(x.atualizado, x.criado) DESC LIMIT ? OFFSET ?",
                         params + [por_pagina, (pagina - 1) * por_pagina]).fetchall()
    return {"itens": [_execucao(r) for r in linhas], "total": total, "pagina": pagina, "por_pagina": por_pagina,
            "paginas": max(1, -(-total // por_pagina))}


def detalhe_execucao(eid: str) -> dict | None:
    con = db.conexao()
    r = con.execute("SELECT x.*, COALESCE(m.arquivada,0) AS arquivada FROM execucoes x "
                    "LEFT JOIN execucao_meta m ON m.execucao_id=x.id WHERE x.id=?", (eid,)).fetchone()
    if not r:
        return None
    d = _execucao(r)
    d["filhas"] = [_execucao(x) | {"arquivada": 0} for x in con.execute(
        "SELECT * FROM execucoes WHERE origem_execucao=? ORDER BY criado DESC", (eid,))]
    pai = con.execute("SELECT * FROM execucoes WHERE id=?", (d["origem_execucao"],)).fetchone() if d["origem_execucao"] else None
    d["pai"] = _execucao(pai) if pai else None
    d["arquivos"] = arquivos_execucao(d["tipo"], d["pasta"])
    if d["tipo"] == "empresas":
        d["empresas"] = con.execute("SELECT COUNT(DISTINCT empresa_id) FROM pesquisas WHERE execucao_id=?", (eid,)).fetchone()[0]
    if d["tipo"] == "instagram":
        d["segmentos"] = segmentos()
    return d


ARQUIVOS = {
    "instagram": [("resultados.csv", "CSV por categoria"), ("arrobas_por_categoria.md", "Lista por categoria (Markdown)"),
                  ("revisao/pacote.md", "Pacote de revisão"), ("revisao/pacote.json", "Pacote de revisão (JSON)"),
                  ("log.txt", "Log da execução")],
    "empresas": [("empresas.xlsx", "Planilha (XLSX)"), ("empresas.csv", "Planilha (CSV)"), ("fontes.csv", "Fontes (CSV)"),
                 ("log.txt", "Log da execução")],
    "revisao_claude": [("log.txt", "Log da revisão"), ("saida.jsonl", "Saída completa (JSON)")],
}


def arquivos_execucao(tipo: str, pasta: str) -> list[dict]:
    from pathlib import Path
    return [{"arquivo": a, "rotulo": r} for a, r in ARQUIVOS.get(tipo, []) if (Path(pasta) / a).is_file()]


def itens_execucao_empresas(eid: str, f: dict) -> dict:
    from empresas.cli import _precisa_revisao
    con = db.conexao()
    params: list = [eid]
    w = ["p.execucao_id=?"]
    if st := _lista(f.get("status")):
        w.append(_em("p.status", st, params))
    if f.get("q"):
        w.append("(p.entrada LIKE ? OR p.nome LIKE ?)")
        params += [f"%{f['q']}%"] * 2
    linhas = con.execute(
        f"SELECT p.id, p.linha, p.entrada, p.status, p.confianca, p.nome, p.cnpj, p.cnpj_confirmado, p.cidade, p.uf, "
        f"p.revisado_em, p.empresa_id, p.registro, e.nome AS empresa_nome FROM pesquisas p LEFT JOIN empresas e ON e.id=p.empresa_id "
        f"WHERE {' AND '.join(w)} ORDER BY p.linha", params).fetchall()
    itens = []
    for r in linhas:
        d = dict(r)
        reg = json.loads(d.pop("registro"))
        d["precisa_revisao"] = _precisa_revisao(reg)
        d["nao_confirmados"] = reg.get("nao_confirmados") or []
        itens.append(d)
    if f.get("revisar") == "1":
        itens = [i for i in itens if i["precisa_revisao"] and not i["revisado_em"]]
    return {"itens": itens, "total": len(itens)}


# ----------------------------------------------------------------------------------------- visão geral e pendências

def visao_geral() -> dict:
    con = db.conexao()
    um = lambda sql, *p: con.execute(sql, p).fetchone()[0]
    limite = (datetime.now() - timedelta(days=config.DIAS_DESATUALIZADA)).isoformat(timespec="seconds")
    seg_ident = {}
    for (s,) in con.execute("SELECT segmentos FROM perfis p WHERE situacao='identificado' AND EXISTS(SELECT 1 FROM perfil_execucao pe2 LEFT JOIN execucao_meta m2 ON m2.execucao_id=pe2.execucao_id WHERE pe2.usuario=p.usuario AND COALESCE(m2.arquivada,0)=0)"):
        for c in _segs(s):
            seg_ident[c] = seg_ident.get(c, 0) + 1
    return {
        "empresas": {
            "total": um("SELECT COUNT(*) FROM empresas WHERE visivel=1"),
            "por_status": {r[0]: r[1] for r in con.execute("SELECT status, COUNT(*) FROM empresas WHERE visivel=1 GROUP BY status")},
            "precisa_revisao": um("SELECT COUNT(*) FROM empresas WHERE visivel=1 AND precisa_revisao=1 AND revisada=0"),
            "com_nao_confirmados": um("SELECT COUNT(*) FROM empresas WHERE visivel=1 AND n_nao_confirmados>0"),
            "desatualizadas": um("SELECT COUNT(*) FROM empresas WHERE visivel=1 AND ultima_pesquisa < ?", limite),
            "sem_contato": um("SELECT COUNT(*) FROM empresas WHERE visivel=1 AND telefone='' AND whatsapp='' AND email=''"),
            "com_perfil": um("SELECT COUNT(DISTINCT empresa_id) FROM vinculos WHERE estado='confirmado'"),
        },
        "perfis": {
            "total": um("SELECT COUNT(*) FROM perfis p WHERE EXISTS(SELECT 1 FROM perfil_execucao pe2 LEFT JOIN execucao_meta m2 ON m2.execucao_id=pe2.execucao_id WHERE pe2.usuario=p.usuario AND COALESCE(m2.arquivada,0)=0)"),
            "identificados": um("SELECT COUNT(*) FROM perfis p WHERE situacao='identificado' AND EXISTS(SELECT 1 FROM perfil_execucao pe2 LEFT JOIN execucao_meta m2 ON m2.execucao_id=pe2.execucao_id WHERE pe2.usuario=p.usuario AND COALESCE(m2.arquivada,0)=0)"),
            "revisar": um("SELECT COUNT(*) FROM perfis p WHERE situacao='revisar' AND EXISTS(SELECT 1 FROM perfil_execucao pe2 LEFT JOIN execucao_meta m2 ON m2.execucao_id=pe2.execucao_id WHERE pe2.usuario=p.usuario AND COALESCE(m2.arquivada,0)=0)"),
            "sem_pesquisa": um("SELECT COUNT(*) FROM perfis p WHERE situacao='identificado' AND EXISTS(SELECT 1 FROM perfil_execucao pe2 LEFT JOIN execucao_meta m2 ON m2.execucao_id=pe2.execucao_id WHERE pe2.usuario=p.usuario AND COALESCE(m2.arquivada,0)=0) AND NOT EXISTS("
                               "SELECT 1 FROM vinculos v WHERE v.usuario=p.usuario AND v.estado='confirmado')"),
            "por_segmento": [s | {"n": seg_ident.get(s["codigo"], 0)} for s in segmentos()],
        },
        "execucoes": {
            "em_andamento": [_execucao(r) for r in con.execute(
                "SELECT * FROM execucoes WHERE em_andamento=1 ORDER BY atualizado DESC")],
            "atencao": [_execucao(r) for r in con.execute(
                "SELECT x.* FROM execucoes x LEFT JOIN execucao_meta m ON m.execucao_id=x.id WHERE COALESCE(m.arquivada,0)=0 "
                "AND x.estado IN ('precisa_acao','parada','pausada','falhou','interrompida','concluida_com_falhas') "
                "ORDER BY x.atualizado DESC LIMIT 10")],
            "recentes": [_execucao(r) for r in con.execute(
                "SELECT x.* FROM execucoes x LEFT JOIN execucao_meta m ON m.execucao_id=x.id WHERE COALESCE(m.arquivada,0)=0 "
                "ORDER BY COALESCE(x.atualizado, x.criado) DESC LIMIT 8")],
            "total": um("SELECT COUNT(*) FROM execucoes"),
        },
        "pendencias": pendencias_resumo(),
    }


def pendencias_resumo() -> dict:
    con = db.conexao()
    um = lambda sql: con.execute(sql).fetchone()[0]
    return {
        "duplicidades": um("SELECT COUNT(*) FROM duplicidades d JOIN empresas a ON a.id=d.a JOIN empresas b ON b.id=d.b "
                           "WHERE d.estado='pendente' AND a.visivel=1 AND b.visivel=1"),
        "vinculos_sugeridos": um("SELECT COUNT(*) FROM vinculos v JOIN empresas e ON e.id=v.empresa_id "
                                 "WHERE v.estado='sugerido' AND e.visivel=1"),
        "empresas_revisar": um("SELECT COUNT(*) FROM empresas WHERE visivel=1 AND precisa_revisao=1 AND revisada=0"),
        # perfis distintos (o mesmo perfil pode estar em várias análises), fora das execuções arquivadas
        "perfis_revisar": um("SELECT COUNT(*) FROM perfis p WHERE situacao='revisar' AND revisado=0 AND EXISTS("
                             "SELECT 1 FROM perfil_execucao pe LEFT JOIN execucao_meta m ON m.execucao_id=pe.execucao_id "
                             "WHERE pe.usuario=p.usuario AND COALESCE(m.arquivada,0)=0)"),
        "perfis_sem_pesquisa": um("SELECT COUNT(*) FROM perfis p WHERE situacao='identificado' AND EXISTS(SELECT 1 FROM perfil_execucao pe2 LEFT JOIN execucao_meta m2 ON m2.execucao_id=pe2.execucao_id WHERE pe2.usuario=p.usuario AND COALESCE(m2.arquivada,0)=0) AND NOT EXISTS("
                                  "SELECT 1 FROM vinculos v WHERE v.usuario=p.usuario AND v.estado='confirmado')"),
        # fila: o mesmo universo, já sem os que você dispensou, e com os que estão sendo pesquisados agora
        "fila_pendentes": um("SELECT COUNT(*) FROM fila_pesquisa WHERE estado='pendente'"),
        "fila_pesquisando": um("SELECT COUNT(*) FROM fila_pesquisa WHERE estado='pesquisando'"),
    }


def pendencias() -> dict:
    con = db.conexao()
    resumo_emp = lambda i: dict(con.execute("SELECT id, nome, cidade, uf, cnpj, cnpj_confirmado, status, confianca, n_pesquisas, "
                                            "site, instagram FROM empresas WHERE id=?", (i,)).fetchone() or {})
    dups = [{"a": d["a"], "b": d["b"], "motivo": d["motivo"], "em": d["em"], "empresa_a": resumo_emp(d["a"]),
             "empresa_b": resumo_emp(d["b"])} for d in con.execute("SELECT d.* FROM duplicidades d JOIN empresas a ON a.id=d.a JOIN empresas b ON b.id=d.b "
                                                                   "WHERE d.estado='pendente' AND a.visivel=1 AND b.visivel=1 ORDER BY d.em DESC LIMIT 200")]
    vinc = [dict(r) | {"segmentos": _segs(r["segmentos"])} for r in con.execute(
        "SELECT v.*, e.nome AS empresa_nome, e.cidade, e.uf, p.nome AS perfil_nome, p.situacao, p.segmentos, p.bio "
        "FROM vinculos v JOIN empresas e ON e.id=v.empresa_id LEFT JOIN perfis p ON p.usuario=v.usuario "
        "WHERE v.estado='sugerido' AND e.visivel=1 ORDER BY v.em DESC LIMIT 200")]
    revisar = []
    # Empresas: só conta a pesquisa exibida de cada empresa (lotes antigos já substituídos não geram pendência).
    emp_pend = {r[0]: r[1] for r in con.execute(
        "SELECT p.execucao_id, COUNT(*) FROM empresas e JOIN pesquisas p ON p.id=e.pesquisa_atual "
        "WHERE e.visivel=1 AND e.precisa_revisao=1 AND e.revisada=0 GROUP BY p.execucao_id")}
    for r in con.execute("SELECT x.* FROM execucoes x LEFT JOIN execucao_meta m ON m.execucao_id=x.id "
                         "WHERE x.tipo IN ('empresas','instagram') AND COALESCE(m.arquivada,0)=0 ORDER BY x.atualizado DESC"):
        x = _execucao(r)
        dados = x["resumo"].get("dados") or {}
        n = emp_pend.get(x["id"], 0) if x["tipo"] == "empresas" else (dados.get("pendentes_revisao") or 0)
        if n > 0:
            revisar.append({"id": x["id"], "tipo": x["tipo"], "nome": x["nome"], "referencia": x["referencia"], "pendentes": n,
                            "estado": x["estado"]})
    return {"duplicidades": dups, "vinculos": vinc, "execucoes_revisar": revisar, "resumo": pendencias_resumo()}
