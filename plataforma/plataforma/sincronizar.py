"""Sincronização das pastas de resultados com o banco de consulta.

As automações continuam gravando em arquivos (fonte da verdade, com checkpoint e retomada). Aqui:
  * o ESTADO de cada execução (pequeno: estado.json/progresso.json) é relido sempre que o arquivo muda;
  * os DADOS (perfis.jsonl, registros.jsonl, correcoes.jsonl) são reimportados quando mudam — no máximo a cada
    INTERVALO_DADOS_EM_ANDAMENTO_S enquanto a execução está em andamento.
A sincronização é idempotente: rodar de novo sem mudanças nos arquivos não altera nada.

Estados normalizados (os originais ficam em status_original):
    criada · em_andamento · aguardando · concluida · concluida_parcial · concluida_com_falhas · interrompida ·
    pausada · parada (processo sumiu sem finalizar) · precisa_acao · falhou
"""

import json
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from plataforma import base, config, db
from plataforma import normalizar as nz

PREFIXO = {"instagram": "ig:", "empresas": "emp:", "revisao_claude": "claude:"}
ESTADOS_ATIVOS = {"em_andamento", "aguardando"}
_lock = threading.Lock()


class ArquivoOcupado(RuntimeError):
    """O arquivo existe mas não pôde ser lido agora (sendo trocado pela automação): tenta no próximo ciclo."""


def _ler_json(caminho: Path, padrao=None):
    for i in range(6):
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return padrao
        except (OSError, ValueError):
            time.sleep(0.05 * (i + 1))
    if caminho.exists():
        raise ArquivoOcupado(caminho.name)
    return padrao


def _assinatura(pasta: Path, nomes) -> str:
    partes = []
    for n in nomes:
        try:
            st = (pasta / n).stat()
            partes.append(f"{n}:{st.st_mtime_ns}:{st.st_size}")
        except OSError:
            partes.append(f"{n}:-")
    return "|".join(partes)


def _segundos_desde(iso: str | None, padrao: float = 1e9) -> float:
    try:
        return (datetime.now() - datetime.fromisoformat(iso)).total_seconds()
    except (TypeError, ValueError):
        return padrao


# ----------------------------------------------------------------------------------------- listagem

def pastas_instagram() -> list[Path]:
    from prospeccao import execucao
    return execucao.listar()


def pastas_empresas() -> list[Path]:
    raiz = config.resultados_empresas()
    if not raiz.exists():
        return []
    return sorted((p for p in raiz.iterdir() if p.is_dir() and any(p.glob("entrada.*"))), reverse=True)


def pastas_claude() -> list[Path]:
    if not config.CLAUDE_DIR.exists():
        return []
    return sorted((p for p in config.CLAUDE_DIR.iterdir() if (p / "config.json").exists()), reverse=True)


def pasta_da_execucao(execucao_id: str) -> tuple[str, Path] | None:
    """('instagram'|'empresas'|'revisao_claude', pasta) a partir do id, sem confiar em caminho vindo de fora."""
    for tipo, pref in PREFIXO.items():
        if execucao_id.startswith(pref):
            nome = execucao_id[len(pref):]
            if not nome or any(c in nome for c in '/\\:*?"<>|') or nome != nome.strip(" .") or nome in (".", ".."):
                return None
            raiz = {"instagram": config.resultados_instagram, "empresas": config.resultados_empresas,
                    "revisao_claude": lambda: config.CLAUDE_DIR}[tipo]()
            pasta = raiz / nome
            try:
                ok = pasta.is_dir() and pasta.resolve().parent == raiz.resolve() and pasta.resolve().name == nome
            except OSError:
                ok = False
            return (tipo, pasta) if ok else None
    return None


# ----------------------------------------------------------------------------------------- estado: Instagram

def estado_instagram(pasta: Path) -> dict:
    from prospeccao import execucao
    _ler_json(pasta / "estado.json")  # levanta ArquivoOcupado se existir e não puder ser lido agora
    est, cfg = execucao.ler_estado(pasta), execucao.ler_config(pasta)
    if (pasta / "estado.json").exists() and not est:
        raise ArquivoOcupado("estado.json")
    origem = _ler_json(pasta / "origem.json", {}) or {}
    st = est.get("status") or "criado"
    parado = bool(est.get("status_exibido"))
    if st in ("executando", "aguardando"):
        estado = "parada" if parado else ("aguardando" if st == "aguardando" else "em_andamento")
    elif st == "concluido":
        estado = "concluida_parcial" if est.get("lista_limitada") else "concluida"
    elif st == "limite_atingido":
        estado = "concluida_parcial"
    elif st == "interrompido":
        estado = "interrompida"
    elif st in execucao.STATUS_TEMPORARIOS:
        estado = "pausada"
    elif st in execucao.STATUS_INTERVENCAO:
        estado = "precisa_acao"
    elif st == "erro":
        estado = "falhou"
    else:
        estado = "criada"
    completa = st == "concluido" and bool(est.get("fim_lista")) and not est.get("lista_limitada")
    pub = est.get("publicacoes") or {}
    obtidos, proc = est.get("obtidos", 0) or 0, est.get("processados", 0) or 0
    pendentes = max(0, obtidos - proc) + max(0, (pub.get("alvos") or 0) - (pub.get("feitos") or 0))
    pode = estado not in ESTADOS_ATIVOS and not completa and not (estado == "concluida_parcial" and est.get("fim_lista"))
    total_publico = origem.get("seguidores")
    alvo = est.get("total_lista") if cfg.get("fonte") == "arquivo" else (
        total_publico if isinstance(total_publico, int) and total_publico > 0 else None)
    if cfg.get("limite"):
        alvo = min(alvo, cfg["limite"]) if alvo else cfg["limite"]
    pct = None
    if est.get("fim_lista") or (cfg.get("limite") and obtidos >= cfg["limite"]):
        pct = 100.0
    elif alvo and not est.get("lista_limitada"):
        pct = round(min(99.9, 100.0 * obtidos / alvo), 1)
    eventos = est.get("eventos") or [{"em": e.get("em"), "tipo": "intervencao", "mensagem": e.get("mensagem")}
                                     for e in est.get("erros", [])]
    resumo = {
        "config": {k: cfg.get(k) for k in ("origem", "categorias", "limite", "detalhes", "publicacoes", "noite", "fonte")},
        "origem": {k: origem.get(k) for k in ("usuario", "nome", "seguidores", "privado")},
        "contadores": {k: est.get(k, 0) for k in ("paginas", "obtidos", "processados", "duplicados", "detalhes_lidos",
                                                   "detalhes_falhos", "privados", "nao_lidos")},
        "publicacoes": pub, "fase": est.get("fase"), "fim_lista": bool(est.get("fim_lista")),
        "lista_limitada": bool(est.get("lista_limitada")), "alvo": alvo, "percentual": pct,
        "estimativa": execucao._estimativa(est), "eventos": eventos[-12:], "retoma_em": est.get("retoma_em"),
        "duracao_s": est.get("duracao_s"), "cursor": est.get("cursor"),
    }
    return {
        "tipo": "instagram", "nome": pasta.name, "referencia": "@" + cfg["origem"] if cfg.get("origem") else "lista importada",
        "estado": estado, "status_original": est.get("status_exibido") or st, "completa": int(completa),
        "pode_retomar": int(pode), "em_andamento": int(estado in ESTADOS_ATIVOS), "criado": cfg.get("criado"),
        "iniciado": est.get("iniciado"), "atualizado": est.get("atualizado"), "finalizado": est.get("finalizado"),
        "total": obtidos, "processados": proc,
        "falhas": (est.get("detalhes_falhos") or 0) + (pub.get("falhas") or 0), "pendentes": pendentes,
        "ultima_etapa": est.get("ultima_etapa") or "", "mensagem": est.get("mensagem") or "", "origem_execucao": None,
        "resumo_estado": resumo,
    }


# ----------------------------------------------------------------------------------------- estado: empresas

def _rotulo_lote(pasta: Path) -> str:
    """'2026-10-19_183505_funerarias-curitiba' -> 'funerarias-curitiba' (nome dado ao lote)."""
    partes = pasta.name.split("_", 2)
    return partes[2] if len(partes) == 3 else pasta.name


def estado_empresas(pasta: Path) -> dict:
    from empresas import entradas, lote
    prog = _ler_json(pasta / "progresso.json", {}) or {}
    meta = _ler_json(pasta / "plataforma.json", {}) or {}
    regs = lote.ler_registros(pasta)
    try:
        total = len(entradas.ler(lote.arquivo_entrada(pasta)))
    except Exception:  # entrada ilegível: usa o que o progresso diz
        total = prog.get("total") or len(regs)
    erros = [r for r in regs.values() if r.get("status") == "erro"]
    st = prog.get("status")
    if not prog:
        estado = "criada"
    elif st == "executando":
        atualizado = prog.get("atualizado")
        if not atualizado:  # lotes de antes do batimento: a hora de gravação do arquivo
            try:
                atualizado = datetime.fromtimestamp((pasta / "progresso.json").stat().st_mtime).isoformat(timespec="seconds")
            except OSError:
                atualizado = None
        estado = "em_andamento" if _segundos_desde(atualizado) < config.SEM_BATIMENTO_EMPRESAS_S else "parada"
    elif st in ("concluido", "concluido_com_erros"):
        estado = "concluida_com_falhas" if erros or len(regs) < total else "concluida"
    elif st == "interrompido":
        estado = "interrompida"
    else:
        estado = "falhou"
    completa = estado == "concluida"
    return {
        "tipo": "empresas", "nome": pasta.name, "referencia": _rotulo_lote(pasta),
        "estado": estado, "status_original": st or "criado", "completa": int(completa),
        "pode_retomar": int(estado not in ESTADOS_ATIVOS and not completa), "em_andamento": int(estado in ESTADOS_ATIVOS),
        "criado": meta.get("criado") or prog.get("iniciado"), "iniciado": prog.get("iniciado"),
        "atualizado": prog.get("atualizado") or prog.get("finalizado") or prog.get("iniciado"),
        "finalizado": prog.get("finalizado"), "total": total, "processados": len(regs) - len(erros), "falhas": len(erros),
        "pendentes": max(0, total - len(regs)) + len(erros),
        "ultima_etapa": (f"pesquisando: {', '.join(prog.get('em_andamento') or [])}" if prog.get("em_andamento")
                         else f"{len(regs)} de {total} pesquisadas"),
        "mensagem": meta.get("descricao", ""), "origem_execucao": meta.get("origem_execucao"),
        "resumo_estado": {"em_andamento": prog.get("em_andamento") or [], "duracao_s": prog.get("duracao_s"),
                          "pid": prog.get("pid"), "erros": [{"linha": r["linha"], "entrada": r["entrada"],
                                                             "observacao": " | ".join(r.get("observacoes") or [])[:300]}
                                                            for r in erros[:50]]},
    }


# ----------------------------------------------------------------------------------------- estado: revisão pelo Claude

def estado_claude(pasta: Path) -> dict:
    cfg = _ler_json(pasta / "config.json", {}) or {}
    est = _ler_json(pasta / "estado.json", {}) or {}
    st = est.get("status") or "criado"
    if st == "executando":
        estado = "em_andamento" if _segundos_desde(est.get("atualizado")) < 180 else "parada"
    else:
        estado = {"concluido": "concluida", "falhou": "falhou", "interrompido": "interrompida", "criado": "criada"}.get(st, "falhou")
    return {
        "tipo": "revisao_claude", "nome": pasta.name, "referencia": cfg.get("descricao", ""), "estado": estado,
        "status_original": st, "completa": int(estado == "concluida"), "pode_retomar": 0,
        "em_andamento": int(estado in ESTADOS_ATIVOS), "criado": cfg.get("criado"), "iniciado": est.get("iniciado"),
        "atualizado": est.get("atualizado"), "finalizado": est.get("finalizado"), "total": cfg.get("max_itens"),
        "processados": est.get("comandos", 0), "falhas": 0, "pendentes": 0,
        "ultima_etapa": est.get("ultima_acao", ""), "mensagem": est.get("mensagem", ""),
        "origem_execucao": cfg.get("alvo"),
        "resumo_estado": {"modo": cfg.get("modo"), "alvo": cfg.get("alvo"), "turnos": est.get("turnos"),
                          "duracao_s": est.get("duracao_s"), "resultado": (est.get("resultado") or "")[:4000]},
    }


# ----------------------------------------------------------------------------------------- dados

def _confianca_max(cats) -> str:
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    return min((c["confianca"] for c in cats), key=lambda c: ordem.get(c, 9), default="")


def dados_instagram(con, eid: str, pasta: Path) -> dict:
    from prospeccao import revisao
    from prospeccao.execucao import _aplicar_correcao, ler_correcoes, resultados

    regs = resultados(pasta)
    corr = ler_correcoes(pasta)
    con.execute("DELETE FROM perfil_execucao WHERE execucao_id=?", (eid,))
    usuarios = []
    cont = Counter()
    por_cat = Counter()
    for r in regs:
        p, cls = r["perfil"], r["classificacao"]
        u = p["usuario"]
        usuarios.append(u)
        cont[cls["situacao"]] += 1
        if cls["situacao"] == "identificado":
            cats = [c for c in cls["categorias"] if c["confianca"] != "baixa"]
            for c in cats:
                por_cat[c["codigo"]] += 1
        else:
            cats = cls["categorias"]
        segs = "," + ",".join(sorted({c["codigo"] for c in cats})) + "," if cats else ""
        revisado = int(bool(cls.get("revisado")))
        con.execute("INSERT INTO perfil_execucao VALUES (?,?,?,?,?,?,?)",
                    (eid, u, cls["situacao"], segs, _confianca_max(cats), revisado, r.get("em") or ""))
        # Registro global do perfil: a classificação sem o filtro de categorias desta execução, com a revisão aplicada.
        glob = _aplicar_correcao(r["classificacao_automatica"], corr.get(u))
        gcats = [c for c in glob["categorias"] if glob["situacao"] != "identificado" or c["confianca"] != "baixa"]
        atual = con.execute("SELECT em, revisado FROM perfis WHERE usuario=?", (u,)).fetchone()
        grev = int(bool(glob.get("revisado")))
        em = r.get("em") or ""
        if atual and (atual["revisado"] > grev or (atual["revisado"] == grev and (atual["em"] or "") > em)):
            continue
        extras = p.get("extras") or {}
        con.execute("""INSERT OR REPLACE INTO perfis(usuario, nome, bio, categoria_ig, conta_comercial, privado, link_externo,
            dominio, seguidores, cidade, telefone, email, situacao, tipo_perfil, estado_analise, segmentos, confianca,
            revisado, classificacao, perfil, execucao_id, em, busca) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            u, p.get("nome", ""), p.get("bio", ""), p.get("categoria_ig", ""),
            None if p.get("conta_comercial") is None else int(p["conta_comercial"]),
            None if p.get("privado") is None else int(p["privado"]), p.get("link_externo", ""),
            nz.chave_dominio(p.get("link_externo")), p.get("seguidores"), extras.get("city_name", ""),
            extras.get("public_phone_number") or extras.get("contact_phone_number") or extras.get("business_phone_number") or "",
            extras.get("public_email") or extras.get("business_email") or "", glob["situacao"], glob.get("tipo_perfil", ""),
            glob.get("estado_analise", ""), "," + ",".join(sorted({c["codigo"] for c in gcats})) + "," if gcats else "",
            _confianca_max(gcats), grev, json.dumps(glob, ensure_ascii=False),
            json.dumps({k: v for k, v in p.items() if k != "posts"} | {"posts": (p.get("posts") or [])[:12]}, ensure_ascii=False),
            eid, em, " ".join(nz.texto(x) for x in (u, p.get("nome"), p.get("bio"), p.get("categoria_ig"),
                                                    extras.get("city_name")) if x)))
    try:
        pendentes_revisao = sum(1 for i in revisao.montar(pasta) if i["estado_revisao"] == "pendente")
    except Exception:
        pendentes_revisao = None
    base.sugerir_vinculos_por_dominio(con, set(usuarios))
    if usuarios:
        afetadas = set()
        for i in range(0, len(usuarios), 900):
            parte = usuarios[i:i + 900]
            afetadas |= {r[0] for r in con.execute(
                f"SELECT DISTINCT empresa_id FROM vinculos WHERE usuario IN ({','.join('?' * len(parte))})", parte)}
        base.recalcular(con, afetadas)
    return {"situacoes": dict(cont), "por_categoria": dict(por_cat), "perfis": len(regs),
            "pendentes_revisao": pendentes_revisao,
            "sem_empresa": con.execute(
                "SELECT COUNT(*) FROM perfil_execucao pe WHERE pe.execucao_id=? AND pe.situacao='identificado' AND NOT EXISTS "
                "(SELECT 1 FROM vinculos v WHERE v.usuario=pe.usuario AND v.estado='confirmado')", (eid,)).fetchone()[0]}


def dados_empresas(con, eid: str, pasta: Path) -> dict:
    from empresas.cli import _precisa_revisao
    from empresas.lote import ler_registros
    from empresas.pesquisa import CAMPOS_ESSENCIAIS

    regs = ler_registros(pasta)
    existentes, chaves_antes = {}, {}
    for r in con.execute("SELECT * FROM pesquisas WHERE execucao_id=?", (eid,)).fetchall():
        existentes[r["id"]] = r["empresa_id"]
        chaves_antes[r["id"]] = base.chaves_da_pesquisa(r)
    afetadas = set()
    vistos = set()
    st, cf = Counter(), Counter()
    origens, dominios, preenchidos = Counter(), Counter(), Counter()
    revisar = revisadas = 0
    for linha, reg in sorted(regs.items()):
        pid = f"{eid}#{linha}"
        vistos.add(pid)
        info = base.identificadores(reg)
        valores = (eid, linha, reg.get("entrada", ""), reg.get("tipo_entrada", ""), reg.get("status", ""),
                   reg.get("confianca", ""), reg.get("data_pesquisa", ""), reg.get("revisado_em"), info["nome"],
                   info["cnpj"], info["cnpj_confirmado"], json.dumps(info["handles"]), json.dumps(info["handles_fortes"]),
                   info["dominio"], info["dominio_confirmado"], info["cidade"], (info["uf"] or "").upper(),
                   json.dumps(reg, ensure_ascii=False))
        if pid in existentes:
            con.execute("""UPDATE pesquisas SET execucao_id=?, linha=?, entrada=?, tipo_entrada=?, status=?, confianca=?, data=?,
                revisado_em=?, nome=?, cnpj=?, cnpj_confirmado=?, handles=?, handles_fortes=?, dominio=?, dominio_confirmado=?,
                cidade=?, uf=?, registro=? WHERE id=?""", valores + (pid,))
        else:
            con.execute("""INSERT INTO pesquisas(execucao_id, linha, entrada, tipo_entrada, status, confianca, data, revisado_em,
                nome, cnpj, cnpj_confirmado, handles, handles_fortes, dominio, dominio_confirmado, cidade, uf, registro, id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", valores + (pid,))
        afetadas |= base.reavaliar(con, pid, chaves_antes[pid]) if pid in existentes else set()
        afetadas |= base.atribuir(con, pid)
        st[reg.get("status", "")] += 1
        cf[reg.get("confianca", "")] += 1
        revisar += bool(_precisa_revisao(reg) and not reg.get("revisado_em"))
        revisadas += bool(reg.get("revisado_em"))
        for campo, itens in (reg.get("campos") or {}).items():
            for i in itens:
                origens[i.get("origem", "")] += 1
                if (i.get("fonte") or "").startswith("http"):
                    dominios[nz.chave_dominio(i["fonte"]) or urlparse(i["fonte"]).hostname or ""] += 1
        for c in CAMPOS_ESSENCIAIS:
            if c not in (reg.get("nao_encontrados") or []):
                preenchidos[c] += 1
    for pid in set(existentes) - vistos:
        con.execute("DELETE FROM pesquisas WHERE id=?", (pid,))
        afetadas.add(existentes[pid])
    for e in afetadas:
        if e is not None:
            base.regenerar_vinculos(con, e)
    base.recalcular(con, afetadas)
    return {"status": dict(st), "confianca": dict(cf), "revisar_pendentes": revisar, "revisadas": revisadas,
            "origens": dict(origens.most_common()), "fontes": dict(dominios.most_common(12)),
            "preenchidos": dict(preenchidos), "registros": len(regs)}


# ----------------------------------------------------------------------------------------- execução de uma pasta

_ARQS_ESTADO = {"instagram": ("estado.json", "config.json", "origem.json"),
                "empresas": ("progresso.json", "registros.jsonl", "plataforma.json"),
                "revisao_claude": ("estado.json", "config.json")}
_ARQS_DADOS = {"instagram": ("perfis.jsonl", "correcoes.jsonl", "config.json"),
               "empresas": ("registros.jsonl",),
               "revisao_claude": ()}


def sincronizar_execucao(con, tipo: str, pasta: Path, forcar: bool = False) -> str:
    """'' (nada mudou), 'estado' ou 'dados'."""
    eid = PREFIXO[tipo] + pasta.name
    atual = con.execute("SELECT assinatura_estado, assinatura_dados, dados_lidos_em, resumo, estado FROM execucoes WHERE id=?",
                        (eid,)).fetchone()
    sig_e = _assinatura(pasta, _ARQS_ESTADO[tipo])
    sig_d = _assinatura(pasta, _ARQS_DADOS[tipo])
    # Estados "em andamento" dependem do relógio (batimento): relê o estado mesmo sem mudança nos arquivos.
    mudou_estado = forcar or not atual or atual["assinatura_estado"] != sig_e or atual["estado"] in ESTADOS_ATIVOS
    mudou_dados = bool(_ARQS_DADOS[tipo]) and (forcar or not atual or atual["assinatura_dados"] != sig_d)
    if not mudou_estado and not mudou_dados:
        return ""
    est = {"instagram": estado_instagram, "empresas": estado_empresas, "revisao_claude": estado_claude}[tipo](pasta)
    resumo = json.loads(atual["resumo"]) if atual and atual["resumo"] else {}
    resumo["estado"] = est.pop("resumo_estado")
    ler_dados = mudou_dados and (forcar or not est["em_andamento"] or not atual
                                 or time.time() - (atual["dados_lidos_em"] or 0) >= config.INTERVALO_DADOS_EM_ANDAMENTO_S)
    with db.transacao() as c:
        if ler_dados:
            resumo["dados"] = (dados_instagram if tipo == "instagram" else dados_empresas)(c, eid, pasta)
        c.execute("""INSERT INTO execucoes(id, tipo, pasta, nome, referencia, estado, status_original, completa, pode_retomar,
            em_andamento, criado, iniciado, atualizado, finalizado, total, processados, falhas, pendentes, ultima_etapa,
            mensagem, origem_execucao, resumo, assinatura_estado, assinatura_dados, dados_lidos_em)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET tipo=excluded.tipo, pasta=excluded.pasta, nome=excluded.nome,
            referencia=excluded.referencia, estado=excluded.estado, status_original=excluded.status_original,
            completa=excluded.completa, pode_retomar=excluded.pode_retomar, em_andamento=excluded.em_andamento,
            criado=excluded.criado, iniciado=excluded.iniciado, atualizado=excluded.atualizado,
            finalizado=excluded.finalizado, total=excluded.total, processados=excluded.processados, falhas=excluded.falhas,
            pendentes=excluded.pendentes, ultima_etapa=excluded.ultima_etapa, mensagem=excluded.mensagem,
            origem_execucao=excluded.origem_execucao, resumo=excluded.resumo, assinatura_estado=excluded.assinatura_estado,
            assinatura_dados=excluded.assinatura_dados, dados_lidos_em=excluded.dados_lidos_em""", (
            eid, tipo, str(pasta), est["nome"], est["referencia"], est["estado"], est["status_original"], est["completa"],
            est["pode_retomar"], est["em_andamento"], est["criado"], est["iniciado"], est["atualizado"], est["finalizado"],
            est["total"], est["processados"], est["falhas"], est["pendentes"], est["ultima_etapa"], est["mensagem"],
            est["origem_execucao"], json.dumps(resumo, ensure_ascii=False), sig_e,
            sig_d if ler_dados or not mudou_dados else (atual["assinatura_dados"] if atual else ""),
            time.time() if ler_dados else (atual["dados_lidos_em"] if atual else None)))
    return "dados" if ler_dados else "estado"


def _remover_execucao(con, eid: str):
    afetadas = {r[0] for r in con.execute("SELECT DISTINCT empresa_id FROM pesquisas WHERE execucao_id=?", (eid,))}
    con.execute("DELETE FROM pesquisas WHERE execucao_id=?", (eid,))
    tinha_perfis = con.execute("SELECT COUNT(*) FROM perfil_execucao WHERE execucao_id=?", (eid,)).fetchone()[0]
    con.execute("DELETE FROM perfil_execucao WHERE execucao_id=?", (eid,))
    if tinha_perfis:
        usuarios = [r[0] for r in con.execute(
            "SELECT usuario FROM perfis WHERE execucao_id=? OR usuario NOT IN (SELECT usuario FROM perfil_execucao)", (eid,))]
        con.execute("DELETE FROM perfis WHERE execucao_id=? OR usuario NOT IN (SELECT usuario FROM perfil_execucao)", (eid,))
        con.execute("UPDATE execucoes SET assinatura_dados='' WHERE tipo='instagram'")  # reimporta quem sobrou
        for i in range(0, len(usuarios), 900):
            parte = usuarios[i:i + 900]
            afetadas |= {r[0] for r in con.execute(
                f"SELECT DISTINCT empresa_id FROM vinculos WHERE usuario IN ({','.join('?' * len(parte))})", parte)}
    con.execute("DELETE FROM execucoes WHERE id=?", (eid,))
    base.recalcular(con, afetadas)


def sincronizar(forcar: bool = False) -> dict:
    """Lê todas as pastas de resultados. Devolve quantas execuções tiveram estado/dados atualizados."""
    with _lock:
        con = db.conexao()
        cont = Counter()
        vistos = set()
        raizes = {"instagram": config.resultados_instagram(), "empresas": config.resultados_empresas(),
                  "revisao_claude": config.CLAUDE_DIR}
        for tipo, pastas in (("instagram", pastas_instagram()), ("empresas", pastas_empresas()),
                             ("revisao_claude", pastas_claude())):
            for pasta in pastas:
                vistos.add(PREFIXO[tipo] + pasta.name)
                try:
                    r = sincronizar_execucao(con, tipo, pasta, forcar)
                except Exception as e:  # uma pasta com problema não impede as outras
                    cont["erros"] += 1
                    _registrar_erro(pasta, e)
                    continue
                if r:
                    cont[r] += 1
        for eid, tipo, caminho in con.execute("SELECT id, tipo, pasta FROM execucoes").fetchall():
            # Removida só se a pasta não existe mais E a pasta raiz está acessível (disco desconectado, variável de
            # ambiente diferente ou pasta recém-criada durante este ciclo não apagam nada).
            if eid in vistos or Path(caminho).exists() or not raizes[tipo].is_dir() or not any(raizes[tipo].iterdir()):
                continue
            with db.transacao() as c:
                _remover_execucao(c, eid)
            cont["removidas"] += 1
        if cont["dados"] or cont["removidas"]:
            from plataforma import fila
            with db.transacao() as c:
                base.sugerir_por_nome(c)
                cont.update(fila.sincronizar_fila(c))
        return dict(cont)


_erros_vistos: dict[str, str] = {}


def _registrar_erro(pasta: Path, e: Exception):
    import logging
    msg = f"{type(e).__name__}: {e}"
    if _erros_vistos.get(str(pasta)) != msg:  # não repete o mesmo erro a cada ciclo
        _erros_vistos[str(pasta)] = msg
        logging.getLogger("plataforma").warning("Falha ao sincronizar %s: %s", pasta.name, msg, exc_info=e)


def arquivar(execucao_id: str, arquivada: bool):
    """Tira (ou devolve) uma execução da base de consulta. Os arquivos não são tocados."""
    with db.transacao() as c:
        if not c.execute("SELECT 1 FROM execucoes WHERE id=?", (execucao_id,)).fetchone():
            raise ValueError("Execução não encontrada.")
        c.execute("INSERT INTO execucao_meta(execucao_id, arquivada) VALUES (?,?) "
                  "ON CONFLICT(execucao_id) DO UPDATE SET arquivada=excluded.arquivada", (execucao_id, int(arquivada)))
        afetadas = {r[0] for r in c.execute("SELECT DISTINCT empresa_id FROM pesquisas WHERE execucao_id=?", (execucao_id,))}
        base.recalcular(c, afetadas)
        from plataforma import fila
        fila.sincronizar_fila(c)  # arquivar/restaurar muda quem é candidato
        base.historico(c, "arquivar", f"Execução {execucao_id} {'arquivada' if arquivada else 'restaurada'}")
