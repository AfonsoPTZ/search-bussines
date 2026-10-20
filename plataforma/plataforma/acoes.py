"""Ações que disparam as automações (sempre como processos separados, que sobrevivem ao fechar a interface).

Cada ação valida a entrada, cria a pasta da execução com as funções da própria automação e inicia o processo com o
mesmo comando que a CLI usaria. O andamento é acompanhado pela sincronização, lendo os arquivos da execução.
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from plataforma import config, db, sincronizar
from plataforma import normalizar as nz


class AcaoInvalida(ValueError):
    pass


_iniciadas: dict[str, float] = {}  # execução -> quando foi (re)iniciada por esta interface
_trava_inicio = threading.Lock()
JANELA_INICIO_S = 90  # tempo para o processo novo gravar "executando"


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def iniciar_processo(args: list[str], cwd: Path, log: Path):
    """Processo independente da interface (outro grupo, sem janela), com a saída no log da execução."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    arq = open(log, "a", encoding="utf-8")
    arq.write(f"\n=== {_agora()} iniciado pela plataforma: {' '.join(Path(a).name if i == 0 else a for i, a in enumerate(args))}\n")
    arq.flush()
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    try:
        return subprocess.Popen(args, cwd=str(cwd), stdout=arq, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                                creationflags=flags | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
    except OSError:  # o terminal não permite sair do "job": inicia normalmente
        return subprocess.Popen(args, cwd=str(cwd), stdout=arq, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                                creationflags=flags)
    finally:
        arq.close()


def _execucao(eid: str) -> tuple[str, Path]:
    achado = sincronizar.pasta_da_execucao(eid)
    if not achado:
        raise AcaoInvalida("Execução não encontrada.")
    return achado


def _ativa(eid: str) -> bool:
    tipo, pasta = _execucao(eid)
    con = db.conexao()
    sincronizar.sincronizar_execucao(con, tipo, pasta)
    r = con.execute("SELECT em_andamento FROM execucoes WHERE id=?", (eid,)).fetchone()
    return bool(r and r[0])


def _registrar(tipo: str, pasta: Path) -> str:
    sincronizar.sincronizar_execucao(db.conexao(), tipo, pasta, forcar=True)
    return sincronizar.PREFIXO[tipo] + pasta.name


# ----------------------------------------------------------------------------------------- Instagram

def iniciar_instagram(dados: dict) -> str:
    from prospeccao import execucao
    from prospeccao.arrobas import ArrobaInvalida

    limite = dados.get("limite")
    try:
        limite = int(limite) if limite not in (None, "", 0, "0") else None
        pasta = execucao.criar(str(dados.get("origem") or ""), dados.get("categorias") or None, limite,
                               dados.get("detalhes") or "candidatos", publicacoes=dados.get("publicacoes") or "duvidosos",
                               noite=bool(dados.get("noite")))
    except (ArrobaInvalida, ValueError) as e:
        raise AcaoInvalida(str(e)) from None
    from prospeccao import config as cfg_ig
    iniciar_processo([config.PYTHON, "-m", "prospeccao", "executar", str(pasta)], cfg_ig.ROOT, pasta / "log.txt")
    return _registrar("instagram", pasta)


# ----------------------------------------------------------------------------------------- empresas

def iniciar_empresas(texto: str, nome: str = "", origem_execucao: str | None = None, descricao: str = "") -> str:
    from empresas import config as cfg_emp
    from empresas import entradas, lote

    linhas = [l for l in (texto or "").replace("\r", "").split("\n") if l.strip()]
    if not linhas:
        raise AcaoInvalida("Informe ao menos uma empresa (uma por linha).")
    if len(linhas) > config.MAX_LINHAS_LOTE:
        raise AcaoInvalida(f"Máximo de {config.MAX_LINHAS_LOTE} empresas por pesquisa; divida a lista.")
    nome = (nome or "").strip()[:60] or "lista"
    destino = config.entradas_empresas()
    destino.mkdir(parents=True, exist_ok=True)
    arq = destino / f"{datetime.now():%Y-%m-%d_%H%M%S}_{lote._slug(nome)}.txt"
    arq.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    if not entradas.ler(arq):
        arq.unlink(missing_ok=True)
        raise AcaoInvalida("Nenhuma empresa reconhecida na lista.")
    for tentativa in range(3):
        try:
            pasta = lote.criar(arq, nome)
            break
        except FileExistsError:  # outra pesquisa criada no mesmo segundo
            time.sleep(1.1)
    else:
        raise AcaoInvalida("Não foi possível criar a pasta da pesquisa; tente de novo.")
    (pasta / "plataforma.json").write_text(json.dumps({
        "criado": _agora(), "criado_por": "plataforma", "origem_execucao": origem_execucao,
        "descricao": descricao or f"{len(linhas)} empresa(s) informadas na plataforma"}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    iniciar_processo([config.PYTHON, "-m", "empresas", "retomar", str(pasta)], cfg_emp.ROOT, pasta / "log.txt")
    return _registrar("empresas", pasta)


def _ja_pesquisada(con, usuario: str, dias: int) -> dict | None:
    r = con.execute("SELECT e.id, e.nome, e.ultima_pesquisa, e.status FROM empresa_chaves k JOIN empresas e ON e.id=k.empresa_id "
                    "WHERE k.chave=?", ("ig:" + usuario,)).fetchone()
    if not r:
        r = con.execute("SELECT e.id, e.nome, e.ultima_pesquisa, e.status FROM vinculos v JOIN empresas e ON e.id=v.empresa_id "
                        "WHERE v.usuario=? AND v.estado='confirmado' ORDER BY e.ultima_pesquisa DESC", (usuario,)).fetchone()
    if r and r["status"] != "erro" and (r["ultima_pesquisa"] or "") >= (datetime.now() - timedelta(days=dias)).isoformat():
        return dict(r)
    return None


def candidatos_da_execucao(eid: str, escopo: str = "identificados", segmentos=None, incluir_pesquisadas: bool = False,
                           dias: int | None = None) -> dict:
    """Perfis de uma análise do Instagram prontos para a pesquisa de empresas (prévia: nada é iniciado aqui)."""
    tipo, _ = _execucao(eid)
    if tipo != "instagram":
        raise AcaoInvalida("A pesquisa de empresas a partir de perfis só vale para análises do Instagram.")
    situacoes = {"identificados": ("identificado",), "todos": ("identificado", "revisar")}.get(escopo)
    if not situacoes:
        raise AcaoInvalida("Escopo inválido: use identificados ou todos.")
    segs = set(segmentos or [])
    dias = config.DIAS_REPESQUISA if dias is None else int(dias)
    con = db.conexao()
    selecionados, pulados = [], []
    linhas = con.execute(
        f"SELECT pe.usuario, pe.situacao, pe.segmentos, p.nome, p.cidade, p.privado FROM perfil_execucao pe "
        f"JOIN perfis p ON p.usuario=pe.usuario WHERE pe.execucao_id=? AND pe.situacao IN ({','.join('?' * len(situacoes))}) "
        f"ORDER BY pe.situacao, pe.segmentos, pe.usuario", (eid, *situacoes)).fetchall()
    for r in linhas:
        cods = {s for s in (r["segmentos"] or "").strip(",").split(",") if s}
        if segs and not cods & segs:
            continue
        _separar_perfil(con, r, cods, incluir_pesquisadas, dias, selecionados, pulados)
    return {"selecionados": selecionados, "pulados": pulados, "dias": dias}


def _separar_perfil(con, r, cods, incluir_pesquisadas, dias, selecionados, pulados):
    """Monta a linha da lista de empresas para um perfil (nome | @ | cidade), ou o pula se já foi pesquisado."""
    item = {"usuario": r["usuario"], "nome": r["nome"] or "", "situacao": r["situacao"], "segmentos": sorted(cods)}
    ja = None if incluir_pesquisadas else _ja_pesquisada(con, r["usuario"], dias)
    if ja:
        pulados.append(item | {"motivo": f"já pesquisada em {ja['ultima_pesquisa'][:10]}", "empresa_id": ja["id"]})
        return
    partes = [nz.nome_para_pesquisa(r["nome"]), "@" + r["usuario"], nz.cidade_para_pesquisa(r["cidade"])]
    item["linha"] = " | ".join(p for p in partes if p)
    selecionados.append(item)


def pesquisar_empresas_de_perfis(usuarios: list[str], incluir_pesquisadas: bool = False, dias: int | None = None) -> str:
    """Pesquisa de empresas a partir de perfis escolhidos na base de perfis (um ou vários)."""
    usuarios = list(dict.fromkeys(u.strip().lstrip("@").lower() for u in usuarios if u and u.strip()))[:500]
    if not usuarios:
        raise AcaoInvalida("Nenhum perfil informado.")
    dias = config.DIAS_REPESQUISA if dias is None else int(dias)
    con = db.conexao()
    selecionados, pulados = [], []
    for u in usuarios:
        r = con.execute("SELECT usuario, nome, cidade, situacao, segmentos FROM perfis WHERE usuario=?", (u,)).fetchone()
        if r:
            _separar_perfil(con, r, {s for s in (r["segmentos"] or "").strip(",").split(",") if s}, incluir_pesquisadas,
                            dias, selecionados, pulados)
    if not selecionados:
        raise AcaoInvalida("Nenhum perfil para pesquisar" + (f" ({len(pulados)} já pesquisados recentemente)." if pulados else "."))
    nome = f"perfil-{selecionados[0]['usuario']}" if len(selecionados) == 1 else "perfis-selecionados"
    return iniciar_empresas("\n".join(i["linha"] for i in selecionados), nome,
                            descricao=f"Empresas de {len(selecionados)} perfil(is) escolhidos na base de perfis"
                                      + (f" ({len(pulados)} pulados: já pesquisados)" if pulados else ""))


def pesquisar_empresas_da_execucao(eid: str, escopo: str = "identificados", segmentos=None,
                                   incluir_pesquisadas: bool = False, dias: int | None = None) -> str:
    cand = candidatos_da_execucao(eid, escopo, segmentos, incluir_pesquisadas, dias)
    if not cand["selecionados"]:
        raise AcaoInvalida("Nenhum perfil para pesquisar com esses critérios"
                           + (f" ({len(cand['pulados'])} já pesquisados recentemente)." if cand["pulados"] else "."))
    r = db.conexao().execute("SELECT referencia FROM execucoes WHERE id=?", (eid,)).fetchone()
    ref = r["referencia"] if r else eid
    rotulo = {"identificados": "identificados", "todos": "identificados e para revisar"}[escopo]
    filtro = f", segmentos {','.join(sorted(segmentos))}" if segmentos else ""
    return iniciar_empresas("\n".join(i["linha"] for i in cand["selecionados"]), f"ig-{ref.lstrip('@')}",
                            origem_execucao=eid,
                            descricao=f"Empresas dos perfis {rotulo} da análise {ref}{filtro} ({len(cand['selecionados'])})")


def pesquisar_fila(limite: int | None = None, segmentos=None, incluir_pesquisadas: bool = False,
                   dias: int | None = None) -> str:
    """Pesquisa de empresas para os perfis pendentes da fila (o passo seguinte da análise do Instagram).

    É o que o comando `/executar-tarefa` do Claude Code e o botão "Pesquisar pendentes" usam.
    """
    from plataforma import fila

    limite = max(1, min(int(limite or config.MAX_LINHAS_LOTE), config.MAX_LINHAS_LOTE))
    dias = config.DIAS_REPESQUISA if dias is None else int(dias)
    con = db.conexao()
    selecionados, pulados = [], []
    for item in fila.listar("pendente", segmentos):
        if len(selecionados) >= limite:
            break
        ja = None if incluir_pesquisadas else _ja_pesquisada(con, item["usuario"], dias)
        if ja:
            pulados.append(item["usuario"])
            continue
        selecionados.append(item)
    if not selecionados:
        raise AcaoInvalida("Nenhum perfil pendente na fila com esses critérios"
                           + (f" ({len(pulados)} já pesquisados nos últimos {dias} dias)." if pulados else "."))
    filtro = f", segmentos {','.join(sorted(segmentos))}" if segmentos else ""
    eid = iniciar_empresas("\n".join(i["linha"] for i in selecionados), "fila",
                           descricao=f"Fila de pesquisa: {len(selecionados)} perfil(is) pendente(s){filtro}"
                                     + (f" ({len(pulados)} pulados: já pesquisados)" if pulados else ""))
    fila.marcar([i["usuario"] for i in selecionados], "pesquisando", lote_id=eid)
    return eid


def atualizar_empresas(ids: list[int]) -> str:
    """Nova pesquisa para empresas já cadastradas, com a mesma entrada da pesquisa exibida (o histórico fica)."""
    if not ids:
        raise AcaoInvalida("Selecione ao menos uma empresa.")
    con = db.conexao()
    linhas, vistos = [], set()
    for i in ids[: config.MAX_LINHAS_LOTE]:
        r = con.execute("SELECT p.entrada FROM empresas e JOIN pesquisas p ON p.id=e.pesquisa_atual WHERE e.id=?", (int(i),)).fetchone()
        if r and r[0] and r[0] not in vistos:
            vistos.add(r[0])
            linhas.append(r[0])
    if not linhas:
        raise AcaoInvalida("Nenhuma das empresas selecionadas tem entrada para repetir a pesquisa.")
    return iniciar_empresas("\n".join(linhas), "atualizacao", descricao=f"Atualização de {len(linhas)} empresa(s) da base")


# ----------------------------------------------------------------------------------------- retomar / parar

def retomar(eid: str, dados: dict | None = None) -> str:
    dados = dados or {}
    tipo, pasta = _execucao(eid)
    with _trava_inicio:
        if time.time() - _iniciadas.get(eid, 0) < JANELA_INICIO_S and not _terminou_depois(eid):
            raise AcaoInvalida("A execução acabou de ser iniciada; aguarde alguns segundos.")
        if _ativa(eid):
            raise AcaoInvalida("A execução já está em andamento.")
        _iniciadas[eid] = time.time()
    return _retomar(eid, tipo, pasta, dados)


def _terminou_depois(eid: str) -> bool:
    """O processo iniciado já terminou (gravou o fim depois de ser iniciado)? Então pode retomar de novo."""
    r = db.conexao().execute("SELECT finalizado, em_andamento FROM execucoes WHERE id=?", (eid,)).fetchone()
    if not r or r["em_andamento"] or not r["finalizado"]:
        return False
    return r["finalizado"] >= datetime.fromtimestamp(_iniciadas.get(eid, 0)).isoformat(timespec="seconds")


def _retomar(eid: str, tipo: str, pasta: Path, dados: dict) -> str:
    if tipo == "instagram":
        from prospeccao import config as cfg_ig
        args = [config.PYTHON, "-m", "prospeccao", "executar", str(pasta)]
        if dados.get("limite") not in (None, ""):
            try:
                limite = int(dados["limite"])
            except ValueError:
                raise AcaoInvalida("Limite inválido.") from None
            if limite < 0:
                raise AcaoInvalida("Limite inválido.")
            args += ["--limite", str(limite)]
        if "noite" in dados:
            args.append("--noite" if dados["noite"] else "--sem-noite")
        iniciar_processo(args, cfg_ig.ROOT, pasta / "log.txt")
    elif tipo == "empresas":
        from empresas import config as cfg_emp
        iniciar_processo([config.PYTHON, "-m", "empresas", "retomar", str(pasta)], cfg_emp.ROOT, pasta / "log.txt")
    else:
        raise AcaoInvalida("Esta execução não pode ser retomada; inicie uma nova revisão.")
    return _registrar(tipo, pasta)


def parar(eid: str) -> str:
    tipo, pasta = _execucao(eid)
    if not _ativa(eid):
        raise AcaoInvalida("A execução não está em andamento.")
    (pasta / "parar").touch()  # as três automações verificam este arquivo e param com segurança
    return eid
