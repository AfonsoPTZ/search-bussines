"""Base de empresas: reconhece a mesma empresa em pesquisas diferentes, liga empresas a perfis do Instagram e
mantém os campos de consulta (filtros) atualizados.

Regras (nada é unido só por nome; nada inferido vira fato):
  * Uma pesquisa entra numa empresa existente quando compartilha uma chave forte (CNPJ confirmado, @ informado ou
    confirmado, site oficial confirmado) ou repete exatamente a mesma entrada, e os CNPJs confirmados não conflitam
    (raízes diferentes = empresas diferentes).
  * Pesquisas que batem com mais de uma empresa ou com conflito de CNPJ geram SUGESTÃO de duplicidade.
  * Nomes iguais/parecidos só geram sugestão de duplicidade, para você decidir (mesma empresa / diferentes).
  * Vínculo empresa ↔ perfil: confirmado quando a pesquisa partiu do @ ou o @ foi confirmado (site oficial linka o
    perfil, revisão); sugerido quando o @ foi achado só pela busca ou o link da bio aponta para o site da empresa.
  * Segmento (A–M): do perfil vinculado e identificado ("perfil") ou inferido pelas regras do Instagram aplicadas ao
    nome/categoria/atividade da empresa ("inferido", sempre exibido como não confirmado).
"""

import json
from datetime import datetime

from plataforma import normalizar as nz

ORDEM_STATUS = {"identificada": 0, "provavel": 1, "parcial": 2, "ambigua": 3, "nao_encontrada": 4, "erro": 5}
_ORIGENS_FORTES_IG = {"entrada", "site", "revisao", "instagram"}


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def historico(con, tipo: str, descricao: str, dados: dict | None = None):
    con.execute("INSERT INTO historico(em, tipo, descricao, dados) VALUES (?,?,?,?)",
                (agora(), tipo, descricao, json.dumps(dados or {}, ensure_ascii=False)))


# ----------------------------------------------------------------------------------------- identificadores

def _ordenados(reg: dict, campo: str) -> list[dict]:
    from empresas.exportar import _ordenar
    return _ordenar(campo, reg.get("campos", {}).get(campo, []))


def _valor(reg: dict, campo: str, so_confirmado=False) -> str:
    for i in _ordenados(reg, campo):
        if not so_confirmado or i.get("confirmado", True):
            return i["valor"]
    return ""


_SEM_SUCESSO = {"ambigua", "nao_encontrada", "erro"}


def _confirmado(i: dict) -> bool:
    """Registros antigos não têm a chave "confirmado": achado só por busca, sem a chave, não conta como confirmado."""
    return i.get("confirmado", i.get("origem") != "busca")


def identificadores(reg: dict) -> dict:
    """O que identifica a empresa de um registro da pesquisa (com o grau de certeza de cada coisa).
    Pesquisa sem sucesso (ambígua, não encontrada, erro) só tem como identificador forte o que foi informado na entrada
    ou confirmado na revisão: o resto pode ser de outra empresa."""
    sucesso = reg.get("status") not in _SEM_SUCESSO
    handles, fortes, fontes_ig = [], [], {}
    for i in _ordenados(reg, "instagram"):
        h = nz.handle_de_url(i["valor"])
        if not h:
            continue
        if h not in handles:
            handles.append(h)
        confirmado = _confirmado(i)
        origens_ok = _ORIGENS_FORTES_IG | ({"busca"} if "confirmado" in i else set()) if sucesso else {"entrada", "revisao"}
        if confirmado and i["origem"] in origens_ok and h not in fortes:
            fortes.append(h)
        fontes_ig.setdefault(h, (i["origem"], i.get("fonte", ""), confirmado))
    site_conf = next((i["valor"] for i in _ordenados(reg, "site") if _confirmado(i)), "") if sucesso else ""
    cnpj_conf = _valor(reg, "cnpj", True) if reg.get("status") == "identificada" else ""
    cnpj_qualquer = _valor(reg, "cnpj")
    pistas = reg.get("pistas") or {}
    return {
        "nome": _valor(reg, "nome_comercial") or pistas.get("nome") or reg.get("entrada", ""),
        "cnpj": nz.cnpj(cnpj_conf or cnpj_qualquer), "cnpj_confirmado": int(bool(cnpj_conf)),
        "handles": handles, "handles_fortes": fortes, "fontes_ig": fontes_ig,
        "dominio": nz.chave_dominio(site_conf or _valor(reg, "site")), "dominio_confirmado": int(bool(site_conf)),
        "cidade": _valor(reg, "cidade") or pistas.get("cidade", ""), "uf": _valor(reg, "uf") or pistas.get("uf", ""),
    }


def chaves_fortes(p) -> list[str]:
    ch = []
    if p["cnpj"] and p["cnpj_confirmado"]:
        ch.append("cnpj:" + p["cnpj"])
    ch += ["ig:" + h for h in json.loads(p["handles_fortes"] or "[]")]
    if p["dominio"] and p["dominio_confirmado"]:
        ch.append("dom:" + p["dominio"])
    return ch


def chave_entrada(p) -> str:
    e = nz.entrada(p["entrada"])
    return "ent:" + e if e else ""


# ----------------------------------------------------------------------------------------- atribuição

def _cnpjs_confirmados(con, empresa_id: int) -> set[str]:
    return {r[0] for r in con.execute(
        "SELECT DISTINCT cnpj FROM pesquisas WHERE empresa_id=? AND cnpj_confirmado=1 AND cnpj<>''", (empresa_id,))}


def conflito_cnpj(con, empresa_id: int, p) -> bool:
    if not (p["cnpj"] and p["cnpj_confirmado"]):
        return False
    outros = _cnpjs_confirmados(con, empresa_id) - {p["cnpj"]}
    return any(c[:8] != p["cnpj"][:8] for c in outros)  # mesma raiz = matriz/filiais da mesma empresa


def conflito_chaves(con, empresa_id: int, p) -> bool:
    """Para unir só pela mesma entrada: CNPJ, site ou @ confirmados diferentes dos da empresa = empresas diferentes."""
    if conflito_cnpj(con, empresa_id, p):
        return True
    chaves = {r[0] for r in con.execute("SELECT chave FROM empresa_chaves WHERE empresa_id=?", (empresa_id,))}
    doms = {c for c in chaves if c.startswith("dom:")}
    igs = {c for c in chaves if c.startswith("ig:")}
    meus = set(chaves_fortes(p))
    meus_dom = {c for c in meus if c.startswith("dom:")}
    meus_ig = {c for c in meus if c.startswith("ig:")}
    return bool(doms and meus_dom and not doms & meus_dom) or bool(igs and meus_ig and not igs & meus_ig)


def registrar_duplicidade(con, a: int, b: int, motivo: str):
    if a == b:
        return
    a, b = sorted((a, b))
    con.execute("INSERT OR IGNORE INTO duplicidades(a, b, motivo, estado, em) VALUES (?,?,?,'pendente',?)",
                (a, b, motivo, agora()))


def _nova_empresa(con) -> int:
    return con.execute("INSERT INTO empresas(criado, visivel) VALUES (?, 1)", (agora(),)).lastrowid


def reavaliar(con, pesquisa_id: str, chaves_antes: set[str]) -> set[int]:
    """Os identificadores de uma pesquisa já atribuída mudaram (ex.: a revisão removeu o @ que a uniu a outra).
    Atribuição manual (unir/separar) nunca é desfeita; a automática é refeita com as chaves atuais."""
    p = con.execute("SELECT * FROM pesquisas WHERE id=?", (pesquisa_id,)).fetchone()
    agora_ = set(chaves_fortes(p)) | ({chave_entrada(p)} - {""})
    if p["empresa_id"] is None or p["separada"] or agora_ == chaves_antes:
        return set()
    antiga = p["empresa_id"]
    outras = set()
    for q in con.execute("SELECT * FROM pesquisas WHERE empresa_id=? AND id<>?", (antiga, pesquisa_id)).fetchall():
        outras |= set(chaves_fortes(q)) | ({chave_entrada(q)} - {""})
    if not outras:  # única pesquisa da empresa: só atualiza as chaves
        for k in chaves_antes - agora_:
            con.execute("DELETE FROM empresa_chaves WHERE chave=? AND empresa_id=?", (k, antiga))
        return atribuir(con, pesquisa_id)
    for k in chaves_antes - outras:  # chaves que só esta pesquisa dava à empresa
        con.execute("DELETE FROM empresa_chaves WHERE chave=? AND empresa_id=?", (k, antiga))
    if not (agora_ & outras):
        con.execute("UPDATE pesquisas SET empresa_id=NULL WHERE id=?", (pesquisa_id,))
        for k in agora_ - outras:
            con.execute("DELETE FROM empresa_chaves WHERE chave=? AND empresa_id=?", (k, antiga))
    return atribuir(con, pesquisa_id) | {antiga}


def chaves_da_pesquisa(p) -> set[str]:
    return set(chaves_fortes(p)) | ({chave_entrada(p)} - {""})


def atribuir(con, pesquisa_id: str) -> set[int]:
    """Associa a pesquisa a uma empresa (existente ou nova). Devolve as empresas afetadas."""
    p = con.execute("SELECT * FROM pesquisas WHERE id=?", (pesquisa_id,)).fetchone()
    fortes = chaves_fortes(p)
    ent = chave_entrada(p)
    donos: list[tuple[int, str]] = []
    for k in fortes:
        r = con.execute("SELECT empresa_id FROM empresa_chaves WHERE chave=?", (k,)).fetchone()
        if r and r[0] not in [d for d, _ in donos]:
            donos.append((r[0], k))
    afetadas = set()
    escolhida = p["empresa_id"]
    ent_conflito = None
    if escolhida is None:
        for eid, _ in donos:
            if not conflito_cnpj(con, eid, p):
                escolhida = eid
                break
        if escolhida is None and not donos and ent:
            r = con.execute("SELECT empresa_id FROM empresa_chaves WHERE chave=?", (ent,)).fetchone()
            if r and not conflito_chaves(con, r[0], p):
                escolhida = r[0]
            elif r:
                ent_conflito = r[0]
        if escolhida is None:
            escolhida = _nova_empresa(con)
        con.execute("UPDATE pesquisas SET empresa_id=? WHERE id=?", (escolhida, pesquisa_id))
        if ent_conflito:
            registrar_duplicidade(con, escolhida, ent_conflito, "mesma entrada, mas site/@/CNPJ confirmados diferentes")
            afetadas.add(ent_conflito)
    for eid, k in donos:
        if eid != escolhida:
            tipo = {"cnpj": "mesmo CNPJ", "ig": "mesmo Instagram", "dom": "mesmo site"}[k.split(":", 1)[0]]
            conflito = conflito_cnpj(con, eid, p)
            registrar_duplicidade(con, escolhida, eid, f"{tipo} ({k.split(':', 1)[1]})"
                                  + (" — mas os CNPJs confirmados são diferentes" if conflito else ""))
            afetadas.add(eid)
    for k in fortes + ([ent] if ent and not ent_conflito else []):
        con.execute("INSERT OR IGNORE INTO empresa_chaves(chave, empresa_id) VALUES (?,?)", (k, escolhida))
    afetadas.add(escolhida)
    return afetadas


# ----------------------------------------------------------------------------------------- vínculos

_EVIDENCIA_IG = {
    "entrada": "A pesquisa da empresa partiu deste @",
    "site": "O site oficial da empresa linka este perfil",
    "revisao": "Perfil confirmado na revisão (com fonte)",
    "instagram": "Perfil confirmado pela pesquisa",
    "busca": "Perfil encontrado pela busca na internet",
}


def _gravar_vinculo(con, usuario, empresa_id, estado, origem, evidencia, fonte=""):
    atual = con.execute("SELECT estado, manual FROM vinculos WHERE usuario=? AND empresa_id=?",
                        (usuario, empresa_id)).fetchone()
    if atual and (atual["manual"] or atual["estado"] == "rejeitado"):
        return  # decisão sua prevalece
    if atual and atual["estado"] == "confirmado" and estado != "confirmado":
        return
    con.execute("INSERT OR REPLACE INTO vinculos(usuario, empresa_id, estado, origem, evidencia, fonte, manual, em) "
                "VALUES (?,?,?,?,?,?,0,?)", (usuario, empresa_id, estado, origem, evidencia, fonte, agora()))


def regenerar_vinculos(con, empresa_id: int):
    """Refaz os vínculos automáticos de uma empresa a partir das pesquisas (os manuais e rejeitados ficam)."""
    con.execute("DELETE FROM vinculos WHERE empresa_id=? AND manual=0 AND estado<>'rejeitado'", (empresa_id,))
    for p in con.execute("SELECT registro, handles_fortes FROM pesquisas WHERE empresa_id=?", (empresa_id,)).fetchall():
        info = identificadores(json.loads(p["registro"]))
        for h in info["handles"]:
            origem, fonte, confirmado = info["fontes_ig"].get(h, ("busca", "", False))
            forte = h in info["handles_fortes"]
            evid = _EVIDENCIA_IG.get(origem, "Encontrado pela pesquisa")
            if not forte:
                evid += " (não confirmado)"
            _gravar_vinculo(con, h, empresa_id, "confirmado" if forte else "sugerido", origem, evid, fonte)
    for (k,) in con.execute("SELECT chave FROM empresa_chaves WHERE empresa_id=? AND chave LIKE 'dom:%'", (empresa_id,)).fetchall():
        for (u,) in con.execute("SELECT usuario FROM perfis WHERE dominio=?", (k[4:],)).fetchall():
            if not con.execute("SELECT 1 FROM vinculos WHERE usuario=? AND empresa_id=?", (u, empresa_id)).fetchone():
                _gravar_vinculo(con, u, empresa_id, "sugerido", "dominio",
                                f"O link da bio do perfil aponta para o site da empresa ({k[4:]})")


def sugerir_vinculos_por_dominio(con, usuarios: list[str] | None = None):
    """Perfis cujo link da bio é o site confirmado de uma empresa: vínculo sugerido (você confirma)."""
    sql = ("SELECT p.usuario, k.empresa_id, p.dominio FROM perfis p JOIN empresa_chaves k ON k.chave = 'dom:' || p.dominio "
           "WHERE p.dominio <> ''")
    for r in con.execute(sql).fetchall():
        if usuarios is not None and r["usuario"] not in usuarios:
            continue
        if not con.execute("SELECT 1 FROM vinculos WHERE usuario=? AND empresa_id=?", (r["usuario"], r["empresa_id"])).fetchone():
            _gravar_vinculo(con, r["usuario"], r["empresa_id"], "sugerido", "dominio",
                            f"O link da bio do perfil aponta para o site da empresa ({r['dominio']})")


def decidir_vinculo(con, usuario: str, empresa_id: int, estado: str, nota: str = ""):
    """estado: confirmado | rejeitado (manual). Também cria o vínculo, se ainda não existir."""
    if estado not in ("confirmado", "rejeitado"):
        raise ValueError("Use confirmado ou rejeitado.")
    if not con.execute("SELECT 1 FROM empresas WHERE id=?", (empresa_id,)).fetchone():
        raise ValueError("Empresa não encontrada.")
    from prospeccao.arrobas import normalizar
    usuario = normalizar(usuario)
    atual = con.execute("SELECT origem, evidencia, fonte FROM vinculos WHERE usuario=? AND empresa_id=?",
                        (usuario, empresa_id)).fetchone()
    evid = (atual["evidencia"] if atual else "Associado manualmente") + (f" · nota: {nota}" if nota else "")
    con.execute("INSERT OR REPLACE INTO vinculos(usuario, empresa_id, estado, origem, evidencia, fonte, manual, em) "
                "VALUES (?,?,?,?,?,?,1,?)", (usuario, empresa_id, estado, atual["origem"] if atual else "manual", evid,
                                              atual["fonte"] if atual else "", agora()))
    historico(con, "vinculo", f"@{usuario} ↔ empresa {empresa_id}: {estado}", {"nota": nota})
    recalcular(con, {empresa_id})


# ----------------------------------------------------------------------------------------- campos de consulta

def segmentos_inferidos(nome: str, textos: list[str], handle: str = "") -> list[str]:
    """Aplica as regras A–M ao nome/atividade da empresa (resultado sempre 'inferido', nunca confirmado).

    A montagem fica em `prospeccao.classificar.segmentos_de_texto`, que é a fonte única das regras.
    """
    from prospeccao.classificar import segmentos_de_texto
    return segmentos_de_texto(nome, textos, handle)


def _seg(codigos) -> str:
    codigos = sorted(set(codigos))
    return "," + ",".join(codigos) + "," if codigos else ""


def data_pesquisa(p) -> str:
    return max(p["revisado_em"] or "", p["data"] or "")


def _melhor(pesquisas: list):
    """A pesquisa exibida: a mais recente (pesquisa ou revisão) que não falhou por erro técnico. Uma pesquisa nova é
    pedida justamente para atualizar os dados, e as versões novas da ferramenta corrigem erros das antigas; as
    anteriores continuam no histórico da empresa."""
    validas = [p for p in pesquisas if p["status"] != "erro"] or pesquisas
    return max(validas, key=data_pesquisa)


def recalcular(con, empresa_ids):
    """Atualiza os campos de exibição/filtro das empresas a partir da melhor pesquisa de cada uma."""
    from empresas.cli import _precisa_revisao
    from empresas.exportar import NOMES_CAMPOS, linha_planilha
    from empresas.pesquisa import CAMPOS_ESSENCIAIS

    arquivadas = {r[0] for r in con.execute("SELECT execucao_id FROM execucao_meta WHERE arquivada=1")}
    for eid in {e for e in empresa_ids if e is not None}:
        todas = con.execute("SELECT * FROM pesquisas WHERE empresa_id=?", (eid,)).fetchall()
        if not todas:
            guarda = (con.execute("SELECT 1 FROM empresa_chaves WHERE empresa_id=? LIMIT 1", (eid,)).fetchone()
                      or con.execute("SELECT 1 FROM vinculos WHERE empresa_id=? AND (manual=1 OR estado='rejeitado') LIMIT 1", (eid,)).fetchone()
                      or con.execute("SELECT 1 FROM duplicidades WHERE (a=? OR b=?) AND estado<>'pendente' LIMIT 1", (eid, eid)).fetchone())
            if guarda:  # a pasta pode ter sido movida e voltar: as pesquisas reencontram esta empresa pelas chaves
                con.execute("UPDATE empresas SET visivel=0, pesquisa_atual=NULL, atualizado=? WHERE id=?", (agora(), eid))
            else:
                con.execute("DELETE FROM empresas WHERE id=?", (eid,))
                con.execute("DELETE FROM vinculos WHERE empresa_id=?", (eid,))
                con.execute("DELETE FROM duplicidades WHERE a=? OR b=?", (eid, eid))
            continue
        visiveis = [p for p in todas if p["execucao_id"] not in arquivadas]
        melhor = _melhor(visiveis or todas)
        reg = json.loads(melhor["registro"])
        linha = linha_planilha(reg)
        bruto = lambda c: linha.get("_bruto_" + c, "")
        info = identificadores(reg)
        nao = sorted(linha["_nao_confirmados"])
        perfis_conf = con.execute(
            "SELECT p.usuario, p.segmentos, p.situacao FROM vinculos v JOIN perfis p ON p.usuario=v.usuario "
            "WHERE v.empresa_id=? AND v.estado='confirmado'", (eid,)).fetchall()
        seg_perfil = [s for r in perfis_conf if r["situacao"] == "identificado" for s in (r["segmentos"] or "").strip(",").split(",") if s]
        handles = sorted({h for p in todas for h in json.loads(p["handles"] or "[]")})
        # Segmento da empresa. Com perfil vinculado e identificado, o segmento dele é a evidência mais específica
        # (uma funerária PET tem CNAE de funerária, mas é E, não F): a inferência só entra sem perfil.
        # Sem perfil, vale primeiro o segmento que a pesquisa já resolveu pelo CNAE/site (dado estruturado) e só
        # depois a inferência pelo nome. Razão social nunca entra ("Funerária Catedral Ltda" não é igreja).
        seg_inf = []
        if not seg_perfil:
            from empresas.categorias import codigo_de_rotulo
            cod = codigo_de_rotulo(bruto("categoria"))
            seg_inf = [cod] if cod else segmentos_inferidos(info["nome"], [bruto("atividade_principal")],
                                                            handles[0] if handles else "")
        datas = [data_pesquisa(p) for p in todas]
        vinculados = [r[0] for r in con.execute("SELECT usuario FROM vinculos WHERE empresa_id=? AND estado<>'rejeitado'", (eid,))]
        busca = " ".join(nz.texto(x) for x in (
            [info["nome"], bruto("razao_social"), bruto("categoria"), bruto("cidade"), bruto("uf"), info["dominio"],
             bruto("site"), bruto("emails")] + [p["entrada"] for p in todas] + handles + vinculados) if x)
        busca += " " + " ".join(nz.cnpj(p["cnpj"]) for p in todas if p["cnpj"])
        con.execute("""UPDATE empresas SET visivel=?, pesquisa_atual=?, nome=?, razao_social=?, categoria=?, cnpj=?,
            cnpj_confirmado=?, cidade=?, cidade_chave=?, uf=?, site=?, dominio=?, instagram=?, telefone=?, whatsapp=?, email=?, status=?,
            confianca=?, completude=?, n_nao_confirmados=?, nao_confirmados=?, nao_encontrados=?, divergencias=?,
            precisa_revisao=?, revisada=?, segmentos_perfil=?, segmentos_inferidos=?, ultima_pesquisa=?, n_pesquisas=?,
            execucoes=?, busca=?, atualizado=? WHERE id=?""", (
            int(bool(visiveis)), melhor["id"], info["nome"], bruto("razao_social"), bruto("categoria"),
            bruto("cnpj"), info["cnpj_confirmado"], info["cidade"], nz.texto(info["cidade"]), (info["uf"] or "").upper(), bruto("site"),
            info["dominio"], bruto("instagram"), bruto("telefones"), bruto("whatsapp"), bruto("emails"), reg["status"],
            reg["confianca"], len(CAMPOS_ESSENCIAIS) - len(reg.get("nao_encontrados") or []), len(nao),
            ", ".join(NOMES_CAMPOS.get(c, c) for c in nao), ", ".join(reg.get("nao_encontrados") or []),
            len(reg.get("divergencias") or []), int(_precisa_revisao(reg)), int(bool(reg.get("revisado_em"))),
            _seg(seg_perfil), _seg(seg_inf), max(datas), len(todas),
            ",".join(sorted({p["execucao_id"] for p in todas})), busca, agora(), eid))


# ----------------------------------------------------------------------------------------- duplicidades

def sugerir_por_nome(con):
    """Empresas com o mesmo nome (sem termos societários) na mesma UF: sugestão para você decidir."""
    grupos: dict[str, list] = {}
    for r in con.execute("SELECT id, nome, uf, cnpj, cnpj_confirmado FROM empresas WHERE visivel=1").fetchall():
        k = nz.chave_nome(r["nome"])
        if len(k) >= 4:
            grupos.setdefault(k, []).append(r)
    for k, g in grupos.items():
        pares = 0
        for i, a in enumerate(g):
            for b in g[i + 1:]:
                if pares >= 10:
                    break
                if a["uf"] and b["uf"] and a["uf"] != b["uf"]:
                    continue
                if a["cnpj_confirmado"] and b["cnpj_confirmado"] and a["cnpj"][:10] != b["cnpj"][:10]:
                    continue  # CNPJs confirmados de raízes diferentes: são empresas diferentes
                registrar_duplicidade(con, a["id"], b["id"], f"mesmo nome ({k})")
                pares += 1


def unir(con, manter: int, remover: int, nota: str = ""):
    """Você decidiu que são a mesma empresa: as pesquisas, chaves e vínculos passam para `manter`."""
    if manter == remover:
        raise ValueError("Escolha duas empresas diferentes.")
    for e in (manter, remover):
        if not con.execute("SELECT 1 FROM empresas WHERE id=?", (e,)).fetchone():
            raise ValueError(f"Empresa {e} não encontrada.")
    con.execute("UPDATE pesquisas SET empresa_id=? WHERE empresa_id=?", (manter, remover))
    con.execute("UPDATE pesquisas SET separada=1 WHERE empresa_id=?", (manter,))  # atribuição manual: não é refeita
    con.execute("UPDATE empresa_chaves SET empresa_id=? WHERE empresa_id=?", (manter, remover))
    for v in con.execute("SELECT * FROM vinculos WHERE empresa_id=? AND (manual=1 OR estado='rejeitado')", (remover,)).fetchall():
        existente = con.execute("SELECT manual, estado FROM vinculos WHERE usuario=? AND empresa_id=?",
                                (v["usuario"], manter)).fetchone()
        if existente and (existente["manual"] or existente["estado"] == "rejeitado"):
            continue  # as duas têm decisão sua: fica a da empresa mantida
        con.execute("INSERT OR REPLACE INTO vinculos(usuario, empresa_id, estado, origem, evidencia, fonte, manual, em) "
                    "VALUES (?,?,?,?,?,?,?,?)", (v["usuario"], manter, v["estado"], v["origem"], v["evidencia"], v["fonte"],
                                                 v["manual"], v["em"]))
    con.execute("DELETE FROM vinculos WHERE empresa_id=?", (remover,))
    for d in con.execute("SELECT * FROM duplicidades WHERE a=? OR b=?", (remover, remover)).fetchall():
        outro = d["b"] if d["a"] == remover else d["a"]
        con.execute("DELETE FROM duplicidades WHERE a=? AND b=?", (d["a"], d["b"]))
        if outro != manter:
            a, b = sorted((manter, outro))
            con.execute("INSERT OR IGNORE INTO duplicidades(a, b, motivo, estado, em) VALUES (?,?,?,?,?)",
                        (a, b, d["motivo"], d["estado"], d["em"]))
    con.execute("DELETE FROM empresas WHERE id=?", (remover,))
    historico(con, "unir", f"Empresa {remover} unida à {manter}", {"nota": nota})
    regenerar_vinculos(con, manter)
    recalcular(con, {manter})


def separar(con, pesquisa_id: str, nota: str = "") -> int:
    """A pesquisa foi associada à empresa errada: vira uma empresa própria (e as duas ficam marcadas como diferentes)."""
    p = con.execute("SELECT * FROM pesquisas WHERE id=?", (pesquisa_id,)).fetchone()
    if not p:
        raise ValueError("Pesquisa não encontrada.")
    antiga = p["empresa_id"]
    if con.execute("SELECT COUNT(*) FROM pesquisas WHERE empresa_id=?", (antiga,)).fetchone()[0] < 2:
        raise ValueError("Esta é a única pesquisa da empresa; não há o que separar.")
    nova = _nova_empresa(con)
    con.execute("UPDATE pesquisas SET empresa_id=?, separada=1 WHERE id=?", (nova, pesquisa_id))
    outras = set()
    for q in con.execute("SELECT * FROM pesquisas WHERE empresa_id=?", (antiga,)).fetchall():
        outras |= set(chaves_fortes(q)) | {chave_entrada(q)}
    for k in set(chaves_fortes(p)) | {chave_entrada(p)}:
        if k and k not in outras:
            con.execute("UPDATE empresa_chaves SET empresa_id=? WHERE chave=?", (nova, k))
    a, b = sorted((antiga, nova))
    con.execute("INSERT OR REPLACE INTO duplicidades(a, b, motivo, estado, em) VALUES (?,?,?,?,?)",
                (a, b, "separadas manualmente", "diferentes", agora()))
    historico(con, "separar", f"Pesquisa {pesquisa_id} separada da empresa {antiga} (nova empresa {nova})", {"nota": nota})
    for e in (antiga, nova):
        regenerar_vinculos(con, e)
    recalcular(con, {antiga, nova})
    return nova


def decidir_duplicidade(con, a: int, b: int, decisao: str, manter: int | None = None, nota: str = ""):
    a, b = sorted((a, b))
    if not con.execute("SELECT 1 FROM duplicidades WHERE a=? AND b=?", (a, b)).fetchone():
        raise ValueError("Sugestão de duplicidade não encontrada.")
    if decisao == "mesma":
        manter = manter if manter in (a, b) else a
        unir(con, manter, b if manter == a else a, nota)
    elif decisao == "diferentes":
        con.execute("UPDATE duplicidades SET estado='diferentes', em=? WHERE a=? AND b=?", (agora(), a, b))
        historico(con, "duplicidade", f"Empresas {a} e {b} marcadas como diferentes", {"nota": nota})
    else:
        raise ValueError("Decisão inválida: use mesma ou diferentes.")
