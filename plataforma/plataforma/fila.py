"""Fila de pesquisa: os perfis que a análise do Instagram identificou e que ainda não têm dados de empresa.

É a ligação entre as duas metades do trabalho:

    Instagram  ->  FILA (pendente)  ->  pesquisa de empresas  ->  base de empresas

A análise de seguidores só descobre *quem* é parceiro em potencial (o @, o nome e o segmento A–M). Quem é
essa empresa de verdade — CNPJ, telefone, endereço, site — vem depois, da pesquisa de empresas. Entre as duas
coisas existe esta fila, para que nada fique pelo caminho e para que dê para retomar o trabalho noutro dia
(ou pelo Claude Code, com `/executar-tarefa`).

A fila é DERIVADA e se mantém sozinha a cada sincronização:
  * entra na fila todo perfil `identificado`, de execução não arquivada, sem empresa confirmada;
  * sai da fila (vira `concluido`) assim que o perfil ganha um vínculo confirmado com uma empresa.
A única parte que é decisão SUA e nunca é desfeita automaticamente é o estado `dispensado`.

Estados: pendente · pesquisando (lote em andamento) · concluido · dispensado.
"""

from plataforma import base, db
from plataforma import normalizar as nz

ESTADOS = ("pendente", "pesquisando", "concluido", "dispensado")


def _segs(v: str | None) -> list[str]:
    return [s for s in (v or "").strip(",").split(",") if s]


def linha_de_pesquisa(nome: str, usuario: str, cidade: str) -> str:
    """A linha que vai para a lista da pesquisa de empresas: 'Nome | @perfil | Cidade/UF'."""
    partes = [nz.nome_para_pesquisa(nome), "@" + usuario, nz.cidade_para_pesquisa(cidade)]
    return " | ".join(p for p in partes if p)


# ----------------------------------------------------------------------------------------- manutenção

_SQL_CANDIDATOS = """
    SELECT p.usuario, p.nome, p.cidade, p.segmentos, p.execucao_id
    FROM perfis p
    WHERE p.situacao='identificado'
      AND EXISTS (SELECT 1 FROM perfil_execucao pe LEFT JOIN execucao_meta m ON m.execucao_id=pe.execucao_id
                  WHERE pe.usuario=p.usuario AND COALESCE(m.arquivada,0)=0)
      AND NOT EXISTS (SELECT 1 FROM vinculos v WHERE v.usuario=p.usuario AND v.estado='confirmado')
"""


def sincronizar_fila(con) -> dict:
    """Põe na fila quem passou a ser candidato e tira quem já tem empresa. Idempotente.

    Nunca mexe em quem você dispensou. Devolve o que mudou, para o log.
    """
    agora = base.agora()
    novos = resolvidos = saidos = 0
    candidatos = {r["usuario"]: r for r in con.execute(_SQL_CANDIDATOS).fetchall()}

    # 1. Entram os candidatos que ainda não estão na fila.
    for usuario, r in candidatos.items():
        existe = con.execute("SELECT estado FROM fila_pesquisa WHERE usuario=?", (usuario,)).fetchone()
        if existe is None:
            con.execute("INSERT INTO fila_pesquisa(usuario, execucao_id, nome, cidade, segmentos, estado, criado, atualizado) "
                        "VALUES (?,?,?,?,?,'pendente',?,?)",
                        (usuario, r["execucao_id"], r["nome"] or "", r["cidade"] or "", r["segmentos"] or "", agora, agora))
            novos += 1
        elif existe["estado"] == "concluido":
            # tinha empresa e deixou de ter (pasta removida, vínculo rejeitado): volta para a fila
            con.execute("UPDATE fila_pesquisa SET estado='pendente', empresa_id=NULL, atualizado=? WHERE usuario=?",
                        (agora, usuario))
        else:  # mantém o estado e a data de entrada; só atualiza o que a análise pode ter melhorado
            con.execute("UPDATE fila_pesquisa SET nome=?, cidade=?, segmentos=?, execucao_id=? WHERE usuario=?",
                        (r["nome"] or "", r["cidade"] or "", r["segmentos"] or "", r["execucao_id"], usuario))

    # 2. Saem os que já têm empresa confirmada, e os que deixaram de ser candidatos (revisão os descartou, a
    #    análise foi arquivada ou a pasta sumiu). Quem você dispensou não é tocado aqui.
    for r in con.execute("SELECT usuario FROM fila_pesquisa WHERE estado IN ('pendente','pesquisando')").fetchall():
        usuario = r["usuario"]
        emp = con.execute("SELECT empresa_id FROM vinculos WHERE usuario=? AND estado='confirmado' LIMIT 1",
                          (usuario,)).fetchone()
        if emp:
            con.execute("UPDATE fila_pesquisa SET estado='concluido', empresa_id=?, atualizado=? WHERE usuario=?",
                        (emp["empresa_id"], agora, usuario))
            resolvidos += 1
        elif usuario not in candidatos:
            con.execute("DELETE FROM fila_pesquisa WHERE usuario=?", (usuario,))
            saidos += 1
    return {k: v for k, v in (("fila_novos", novos), ("fila_resolvidos", resolvidos), ("fila_saidos", saidos)) if v}


# ----------------------------------------------------------------------------------------- consulta

def listar(estado: str = "pendente", segmentos=None, execucao: str = "", limite: int | None = None) -> list[dict]:
    """Itens da fila, os mais antigos primeiro (quem espera há mais tempo sai na frente)."""
    con = db.conexao()
    w, params = [], []
    if estado and estado != "todos":
        if estado not in ESTADOS:
            raise ValueError(f"Estado inválido: {estado}. Use {' | '.join(ESTADOS)} ou todos.")
        w.append("f.estado=?")
        params.append(estado)
    if execucao:
        w.append("f.execucao_id=?")
        params.append(execucao)
    segs = [s.strip().upper() for s in (segmentos or []) if s and s.strip()]
    if segs:
        w.append("(" + " OR ".join("f.segmentos LIKE ?" for _ in segs) + ")")
        params += [f"%,{s},%" for s in segs]
    sql = ("SELECT f.*, x.referencia AS analise FROM fila_pesquisa f "
           "LEFT JOIN execucoes x ON x.id=f.execucao_id"
           + ((" WHERE " + " AND ".join(w)) if w else "")
           + " ORDER BY f.criado, f.usuario")
    if limite:
        sql += " LIMIT ?"
        params.append(int(limite))
    saida = []
    for r in con.execute(sql, params):
        d = dict(r)
        d["segmentos"] = _segs(d["segmentos"])
        d["linha"] = linha_de_pesquisa(d["nome"], d["usuario"], d["cidade"])
        saida.append(d)
    return saida


def resumo() -> dict:
    con = db.conexao()
    por_estado = {e: 0 for e in ESTADOS}
    for estado, n in con.execute("SELECT estado, COUNT(*) FROM fila_pesquisa GROUP BY estado"):
        por_estado[estado] = n
    por_segmento = {}
    for (s,) in con.execute("SELECT segmentos FROM fila_pesquisa WHERE estado='pendente'"):
        for c in _segs(s):
            por_segmento[c] = por_segmento.get(c, 0) + 1
    return {"por_estado": por_estado, "pendentes": por_estado["pendente"], "por_segmento": por_segmento,
            "total": sum(por_estado.values())}


# ----------------------------------------------------------------------------------------- decisões

def marcar(usuarios: list[str], estado: str, lote_id: str = "", motivo: str = "") -> int:
    """Muda o estado de itens da fila. 'pesquisando' também conta uma tentativa."""
    if estado not in ESTADOS:
        raise ValueError(f"Estado inválido: {estado}. Use {' | '.join(ESTADOS)}.")
    usuarios = [u.strip().lstrip("@").lower() for u in usuarios if u and u.strip()]
    if not usuarios:
        return 0
    n = 0
    with db.transacao() as con:
        for u in usuarios:
            cur = con.execute(
                "UPDATE fila_pesquisa SET estado=?, lote_id=COALESCE(NULLIF(?,''), lote_id), motivo=?, atualizado=?, "
                "tentativas=tentativas + ? WHERE usuario=?",
                (estado, lote_id, motivo, base.agora(), 1 if estado == "pesquisando" else 0, u))
            n += cur.rowcount
        if estado == "dispensado":
            base.historico(con, "fila", f"{n} perfil(is) dispensado(s) da fila de pesquisa", {"motivo": motivo})
    return n


def dispensar(usuario: str, motivo: str = "") -> int:
    """Decisão sua: este perfil não precisa de pesquisa de empresa. Não volta sozinho para a fila."""
    return marcar([usuario], "dispensado", motivo=motivo or "dispensado manualmente")


def reabrir(usuario: str) -> int:
    """Devolve à fila um perfil dispensado."""
    return marcar([usuario], "pendente", motivo="")
