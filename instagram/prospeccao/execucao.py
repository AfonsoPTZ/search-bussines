"""Execução de uma análise em fases, com checkpoint: tudo que é obtido é gravado na hora e a retomada não repete nada.

Fases (cada uma retomável; a fase atual é deduzida dos arquivos, não só do estado):
    1. lista        percorre a lista de seguidores (páginas de ~25), deduplica e faz a triagem de cada @
                    → seguidores.jsonl (um por @, com prioridade de leitura)
    2. perfis       analisa os seguidores em ORDEM DE PRIORIDADE (segmento → comercial → profissional → indefinido →
                    pessoa); lê bio/categoria de quem a triagem indicar e classifica → perfis.jsonl
    3. publicacoes  para duvidosos e contas comerciais sem categoria: lê fixados + últimas publicações (legendas,
                    hashtags, local) e, se ainda inconclusivo, os títulos dos destaques; reclassifica → perfis.jsonl
    4. fim          gera CSV, lista Markdown e o pacote de revisão

Estrutura (resultados/<data>_<origem>/):
    config.json        origem, categorias, limite, modo de leitura, publicações, modo noite
    origem.json        perfil de origem (id, total público de seguidores)
    lista.txt          (modo arquivo) @s importados
    seguidores.jsonl   fase 1 (só acréscimo)
    perfis.jsonl       fases 2 e 3 (só acréscimo; vale o último registro de cada @)
    correcoes.jsonl    decisões da revisão
    estado.json        fase, cursor, contadores, eventos (temporários x que exigem ação), tempo
    revisao/           pacote de revisão (JSON + Markdown)
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from prospeccao import categorias as cats
from prospeccao import config, triagem
from prospeccao.arrobas import normalizar
from prospeccao.classificar import classificar, filtrar, precisa_publicacoes
from prospeccao.coleta import (ErroAutenticacao, ErroColeta, ErroDesafio, ErroIndisponivel, ErroLimite, ErroPerfil,
                               ErroSemSessao, Pagina)
from prospeccao.perfis import Perfil

MODOS_DETALHES = {
    "candidatos": "lê bio/categoria de quem pode ser empresa: indício no @/nome, nome comercial ou indefinido (recomendado)",
    "todos": "lê bio/categoria de todos os perfis públicos, inclusive nomes de pessoa (mais lento)",
    "nenhum": "classifica só pelo @ e nome (rápido; nada sai com confiança alta)",
}
MODOS_PUBLICACOES = {
    "duvidosos": "lê publicações dos duvidosos e das contas comerciais sem categoria (recomendado)",
    "nenhuma": "não lê publicações",
}
STATUS_TEMPORARIOS = {"pausado_limite_instagram", "erro_rede", "aguardando"}
STATUS_INTERVENCAO = {"erro_desafio", "erro_autenticacao", "sem_sessao", "erro_perfil"}
FINAIS = {"concluido", "limite_atingido", "interrompido", "erro"} | STATUS_TEMPORARIOS | STATUS_INTERVENCAO
SEM_ATUALIZACAO_S = 20 * 60


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", t.lower()).strip("-")[:40] or "analise"


def _gravar_json(caminho: Path, dados):
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    for i in range(40):  # no Windows, quem está lendo o arquivo (painel, plataforma) impede a troca por instantes
        try:
            tmp.replace(caminho)
            return
        except PermissionError:
            if i == 39:
                raise
            time.sleep(0.05 * (1 + i % 5))


def pid_vivo(pid) -> bool:
    """O processo ainda existe? (sem sinal: no Windows, os.kill(pid, 0) interromperia o processo)"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            codigo = ctypes.c_ulong()
            return bool(k.GetExitCodeProcess(h, ctypes.byref(codigo))) and codigo.value == 259  # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class AnaliseEmUso(RuntimeError):
    pass


def _travar(pasta: Path) -> Path:
    """Um só processo por análise: dois 'retomar' seguidos não leem (nem gravam) em dobro."""
    trava = pasta / "executando.lock"
    for _ in range(2):
        try:
            fd = os.open(trava, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return trava
        except FileExistsError:
            try:
                dono = trava.read_text(encoding="utf-8").strip()
            except OSError:
                dono = ""
            if dono and pid_vivo(dono):
                raise AnaliseEmUso(f"A análise já está em execução em outro processo (pid {dono}).")
            trava.unlink(missing_ok=True)  # trava de um processo que morreu
    raise AnaliseEmUso("Não foi possível reservar a análise; tente de novo.")


def _ler_json(caminho: Path, padrao=None):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def _iterar_jsonl(caminho: Path):
    if not caminho.exists():
        return
    with caminho.open(encoding="utf-8") as f:
        for linha in f:
            if linha.strip():
                try:
                    yield json.loads(linha)
                except json.JSONDecodeError:
                    continue  # linha truncada por interrupção


def _abrir_acrescimo(caminho: Path):
    """Abre um .jsonl para acréscimo; se o processo morreu no meio de uma linha, isola o pedaço inválido."""
    if caminho.exists() and caminho.stat().st_size:
        with caminho.open("rb") as f:
            f.seek(-1, 2)
            truncada = f.read(1) != b"\n"
        if truncada:
            with caminho.open("a", encoding="utf-8") as f:
                f.write("\n")
    return caminho.open("a", encoding="utf-8")


def _gravar_linha(arq, dados, sincronizar=False):
    arq.write(json.dumps(dados, ensure_ascii=False) + "\n")
    arq.flush()
    if sincronizar:
        try:
            os.fsync(arq.fileno())  # sobrevive a queda de energia, não só a fechar o programa
        except OSError:
            pass


def criar(origem: str, categorias=None, limite: int | None = None, detalhes: str = "candidatos",
          arquivo_lista: Path | None = None, nome: str | None = None, publicacoes: str = "duvidosos",
          noite: bool = False) -> Path:
    from prospeccao.coleta import ler_lista_arquivo

    if detalhes not in MODOS_DETALHES:
        raise ValueError(f"Modo de detalhes inválido: {detalhes}. Use: {', '.join(MODOS_DETALHES)}")
    if publicacoes not in MODOS_PUBLICACOES:
        raise ValueError(f"Modo de publicações inválido: {publicacoes}. Use: {', '.join(MODOS_PUBLICACOES)}")
    if limite is not None and limite <= 0:
        raise ValueError("O limite precisa ser um número positivo.")
    codigos = cats.resolver(categorias)
    usuario = normalizar(origem) if origem else ""
    lista = ler_lista_arquivo(arquivo_lista) if arquivo_lista else None
    if arquivo_lista and not lista:
        raise ValueError("Nenhum @ válido encontrado no arquivo.")
    if not usuario and lista is None:
        raise ValueError("Informe o @ de origem.")
    config.RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)
    pasta = config.RESULTADOS_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}_{_slug(nome or usuario or Path(arquivo_lista).stem)}"
    pasta.mkdir(parents=True, exist_ok=False)
    if lista is not None:
        (pasta / "lista.txt").write_text("\n".join(lista) + "\n", encoding="utf-8")
    _gravar_json(pasta / "config.json", {
        "origem": usuario, "categorias": codigos, "limite": limite, "detalhes": detalhes, "publicacoes": publicacoes,
        "noite": bool(noite), "fonte": "arquivo" if lista is not None else "instagram", "arquivo": str(arquivo_lista or ""),
        "criado": agora()})
    _gravar_json(pasta / "estado.json", {"status": "criado", "fase": "lista", "atualizado": agora(), "cursor": None,
                                         "paginas": 0, "obtidos": 0, "processados": 0, "duplicados": 0,
                                         "detalhes_lidos": 0, "detalhes_falhos": 0, "privados": 0, "nao_lidos": 0,
                                         "fim_lista": False, "lista_limitada": False, "erros": [], "eventos": [],
                                         "publicacoes": {"alvos": 0, "feitos": 0, "lidas": 0, "falhas": 0, "destaques": 0},
                                         "mensagem": ""})
    return pasta


def ler_config(pasta: Path) -> dict:
    return _ler_json(pasta / "config.json", {})


def ler_estado(pasta: Path) -> dict:
    est = _ler_json(pasta / "estado.json", {}) or {}
    if est.get("status") in ("executando", "aguardando"):
        try:
            dt = datetime.fromisoformat(est.get("atualizado", ""))
            if (datetime.now() - dt).total_seconds() > SEM_ATUALIZACAO_S:
                est["status_exibido"] = "parado (sem atualização; use Retomar)"
        except ValueError:
            pass
    return est


def iterar_registros(pasta: Path):
    yield from _iterar_jsonl(pasta / "perfis.jsonl")


def iterar_seguidores(pasta: Path):
    yield from _iterar_jsonl(pasta / "seguidores.jsonl")


def ler_correcoes(pasta: Path) -> dict[str, dict]:
    corr = {}
    for c in _iterar_jsonl(pasta / "correcoes.jsonl"):
        if "usuario" in c:
            corr[c["usuario"]] = c
    return corr


def corrigir(pasta: Path, usuario: str, categorias_corretas: list[str] | None, nota: str = "", descartar=False,
             revisor: str = "manual"):
    """Revisão humana (ou pelo Claude no chat): fixa as categorias de um perfil ou o descarta."""
    usuario = normalizar(usuario)
    if not any(r["perfil"]["usuario"] == usuario for r in iterar_registros(pasta)):
        raise ValueError(f"@{usuario} não foi analisado nesta execução.")
    reg = {"usuario": usuario, "categorias": [] if descartar else cats.resolver(categorias_corretas),
           "descartar": descartar, "nota": nota, "revisor": revisor, "em": agora()}
    with _abrir_acrescimo(pasta / "correcoes.jsonl") as f:
        _gravar_linha(f, reg)


def _aplicar_correcao(cls: dict, c: dict | None) -> dict:
    if not c:
        return cls
    if c["descartar"]:
        return dict(cls, categorias=[], situacao="descartado", revisao=c.get("nota", ""), revisado=True)
    existentes = {x["codigo"]: x for x in cls["categorias"]}
    novas = []
    for cod in c["categorias"]:
        base = existentes.get(cod, {"codigo": cod, "nome": cats.POR_CODIGO[cod].nome, "pontuacao": 0, "evidencias": []})
        novas.append(dict(base, confianca="alta", evidencias=base["evidencias"] + [f"revisão: {c.get('nota') or 'confirmado'}"]))
    return dict(cls, categorias=novas, situacao="identificado" if novas else "descartado", revisao=c.get("nota", ""),
                revisado=True)


def ultimos_registros(pasta: Path) -> dict[str, dict]:
    ultimos = {}
    for r in iterar_registros(pasta):
        ultimos[r["perfil"]["usuario"]] = r
    return ultimos


def resultados(pasta: Path) -> list[dict]:
    """Registros finais (último de cada @), filtrados pelas categorias da execução e com as correções aplicadas."""
    codigos = ler_config(pasta).get("categorias") or cats.CODIGOS
    corr = ler_correcoes(pasta)
    saida = []
    for u, r in ultimos_registros(pasta).items():
        cls = _aplicar_correcao(filtrar(r["classificacao"], codigos), corr.get(u))
        saida.append({"perfil": r["perfil"], "classificacao": cls, "classificacao_automatica": r["classificacao"],
                      "em": r.get("em")})
    return saida


def _estimativa(est: dict) -> dict | None:
    """Tempo restante da fase atual, medido pelo ritmo real desta execução (é só estimativa)."""
    pf = est.get("progresso_fase") or {}
    if est.get("status") not in ("executando", "aguardando") or not pf.get("total") or not pf.get("inicio"):
        return None
    try:
        gasto = (datetime.now() - datetime.fromisoformat(pf["inicio"])).total_seconds()
    except ValueError:
        return None
    feitos_agora = pf.get("feitos", 0) - pf.get("feitos_no_inicio", 0)
    if feitos_agora < 5 or gasto < 30:
        return None
    restante = max(0, pf["total"] - pf.get("feitos", 0)) * gasto / feitos_agora
    return {"fase": pf.get("fase"), "restante_s": round(restante), "ritmo_por_min": round(60 * feitos_agora / gasto, 1)}


def resumo(pasta: Path) -> dict:
    est, cfg = ler_estado(pasta), ler_config(pasta)
    origem = _ler_json(pasta / "origem.json", {}) or {}
    regs = resultados(pasta)
    por_cat = {c: {"identificados": [], "revisar": []} for c in cfg.get("categorias", [])}
    for r in regs:
        cls = r["classificacao"]
        for c in cls["categorias"]:
            if c["codigo"] in por_cat:
                chave = "identificados" if cls["situacao"] == "identificado" and c["confianca"] != "baixa" else "revisar"
                por_cat[c["codigo"]][chave].append((r, c))
    for v in por_cat.values():
        for k in v:
            v[k].sort(key=lambda rc: (-rc[1]["pontuacao"], rc[0]["perfil"]["usuario"]))
    ident = sum(1 for r in regs if r["classificacao"]["situacao"] == "identificado")
    rev = sum(1 for r in regs if r["classificacao"]["situacao"] == "revisar")
    sem_info = sum(1 for r in regs if r["classificacao"]["estado_analise"] in ("so_nome", "detalhes_indisponiveis", "privado"))
    com_posts = sum(1 for r in regs if "publicacoes" in (r["perfil"].get("etapas") or []))
    total_publico = origem.get("seguidores")
    alvo = est.get("total_lista") if cfg.get("fonte") == "arquivo" else (
        total_publico if isinstance(total_publico, int) and total_publico > 0 else None)
    if alvo and cfg.get("limite"):
        alvo = min(alvo, cfg["limite"])
    elif cfg.get("limite") and not alvo:
        alvo = cfg["limite"]
    pct = None  # progresso da coleta da lista (fase 1)
    if est.get("fim_lista") or (cfg.get("limite") and est.get("obtidos", 0) >= cfg["limite"]):
        pct = 100.0
    elif alvo and not est.get("lista_limitada"):
        pct = min(99.9, 100.0 * est.get("obtidos", 0) / alvo)
    return {"pasta": pasta, "config": cfg, "estado": est, "origem": origem, "registros": regs, "por_categoria": por_cat,
            "identificados": ident, "revisar": rev, "sem_informacao": sem_info, "com_publicacoes": com_posts,
            "alvo": alvo, "percentual": pct, "estimativa": _estimativa(est)}


class _Execucao:
    def __init__(self, pasta: Path, cliente, saida, dormir=time.sleep):
        self.pasta, self.cliente, self.saida, self.dormir = pasta, cliente, saida, dormir
        self.cfg = ler_config(pasta)
        self.cfg_triagem = triagem.carregar_config()
        self.est = _ler_json(pasta / "estado.json", {}) or {}
        self.est.pop("status_exibido", None)
        self.est.setdefault("publicacoes", {"alvos": 0, "feitos": 0, "lidas": 0, "falhas": 0, "destaques": 0})
        self.est.setdefault("eventos", [])
        self.limite = self.cfg.get("limite")
        self._base_s = self.est.get("duracao_s", 0) or 0
        self._t0 = time.monotonic()
        self._migrar_analise_antiga()
        self.ordem = {}  # @ -> posição na lista (para manter a ordem original dentro de cada prioridade)
        self.seguidores = {}
        for i, s in enumerate(iterar_seguidores(pasta)):
            self.seguidores.setdefault(s["usuario"], s)
            self.ordem.setdefault(s["usuario"], i)
        self.analisados = {r["perfil"]["usuario"] for r in iterar_registros(pasta)}

    # ---------- estado

    def salvar(self, **mudancas):
        self.est.update(mudancas, atualizado=agora(), pid=os.getpid(),
                        duracao_s=round(self._base_s + time.monotonic() - self._t0))
        _gravar_json(self.pasta / "estado.json", self.est)

    def evento(self, tipo: str, msg: str):
        """tipo: temporario (a ferramenta espera/retoma), intervencao (precisa de você) ou info."""
        self.est.setdefault("eventos", []).append({"em": agora(), "tipo": tipo, "mensagem": msg})
        self.est["eventos"] = self.est["eventos"][-100:]
        if tipo != "info":
            self.est.setdefault("erros", []).append({"em": agora(), "mensagem": msg})
            self.est["erros"] = self.est["erros"][-50:]

    def erro(self, msg: str):  # compatibilidade
        self.evento("intervencao", msg)

    def pedido_parada(self) -> bool:
        return (self.pasta / "parar").exists()

    def avisar(self, msg: str):
        self.saida(f"  · {msg}")
        self.salvar(mensagem=msg)

    def _fase(self, fase: str, total: int, feitos: int):
        pf = self.est.get("progresso_fase") or {}
        if pf.get("fase") != fase or pf.get("pid") != os.getpid():
            pf = {"fase": fase, "inicio": agora(), "feitos_no_inicio": feitos, "pid": os.getpid()}
        pf.update(total=total, feitos=feitos)
        self.est["progresso_fase"] = pf
        self.est["fase"] = fase

    def _migrar_analise_antiga(self):
        """Análises feitas antes das fases não têm seguidores.jsonl: reconstrói a partir de perfis.jsonl."""
        seg = self.pasta / "seguidores.jsonl"
        if seg.exists() or not (self.pasta / "perfis.jsonl").exists():
            return
        with _abrir_acrescimo(seg) as f:
            vistos = set()
            for r in iterar_registros(self.pasta):
                p = Perfil.de_dict(r["perfil"])
                if p.usuario in vistos:
                    continue
                vistos.add(p.usuario)
                pr, mot = triagem.avaliar(Perfil(usuario=p.usuario, nome=p.nome, privado=p.privado), self.cfg_triagem)
                _gravar_linha(f, {"usuario": p.usuario, "pk": p.pk, "nome": p.nome, "privado": p.privado,
                                  "verificado": p.verificado, "triagem": {"prioridade": pr, "motivo": mot}})
        self.evento("info", "análise anterior às fases: lista de seguidores reconstruída a partir dos perfis já analisados")

    # ---------- fase 1: lista de seguidores

    def _limite_lista_atingido(self) -> bool:
        return bool(self.limite) and len(self.seguidores) >= self.limite

    def _paginas_arquivo(self):
        lista = [l.strip() for l in (self.pasta / "lista.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
        self.est["total_lista"] = len(lista)
        inicio = int(self.est.get("cursor") or 0)
        for i in range(inicio, len(lista), config.TAMANHO_PAGINA):
            fim = i + config.TAMANHO_PAGINA
            yield Pagina(perfis=[Perfil(usuario=u) for u in lista[i:fim]], proximo=str(fim) if fim < len(lista) else None)

    def _origem(self) -> dict:
        origem = _ler_json(self.pasta / "origem.json")
        if not origem:
            self.salvar(mensagem=f"lendo o perfil de origem @{self.cfg['origem']}")
            origem = self.cliente.perfil_origem(self.cfg["origem"])
            _gravar_json(self.pasta / "origem.json", origem)
            self.saida(f"Origem @{origem['usuario']} (id {origem['pk']}): {origem.get('seguidores', '?')} seguidores públicos")
        if origem.get("privado") and not origem.get("sigo"):
            raise ErroPerfil(f"@{origem['usuario']} é privado e a conta logada não o segue: a lista não é acessível.")
        return origem

    def _paginas_instagram(self):
        origem = self._origem()
        cursor = self.est.get("cursor")
        while True:
            pag = self.cliente.pagina_seguidores(origem["pk"], origem["usuario"], cursor)
            yield pag
            if not pag.proximo:
                return
            cursor = pag.proximo

    def fase_lista(self):
        if self.est.get("fim_lista") or self._limite_lista_atingido():
            return
        if self.cfg.get("fonte") != "arquivo" and self.cliente is None:
            raise ErroSemSessao("Sessão do Instagram não configurada. Rode: prospeccao sessao firefox (ou sessao definir)")
        origem = _ler_json(self.pasta / "origem.json") or {}
        fonte = self._paginas_arquivo() if self.cfg.get("fonte") == "arquivo" else self._paginas_instagram()
        with _abrir_acrescimo(self.pasta / "seguidores.jsonl") as arq:
            for pag in fonte:
                origem = origem or _ler_json(self.pasta / "origem.json") or {}
                total = self.est.get("total_lista") or origem.get("seguidores") or 0
                self.est["paginas"] = self.est.get("paginas", 0) + 1
                if pag.limitada:
                    self.est["lista_limitada"] = True
                cortou = False
                for p in pag.perfis:
                    if self._limite_lista_atingido():
                        cortou = True
                        break
                    if p.usuario in self.seguidores:
                        self.est["duplicados"] = self.est.get("duplicados", 0) + 1
                        continue
                    pr, mot = triagem.avaliar(p, self.cfg_triagem)
                    linha = {"usuario": p.usuario, "pk": p.pk, "nome": p.nome, "privado": p.privado,
                             "verificado": p.verificado, "triagem": {"prioridade": pr, "motivo": mot}}
                    self.seguidores[p.usuario] = linha
                    self.ordem[p.usuario] = len(self.ordem)
                    _gravar_linha(arq, linha)
                try:
                    os.fsync(arq.fileno())  # página inteira em disco antes de avançar o cursor
                except OSError:
                    pass
                self.est["obtidos"] = len(self.seguidores)
                alvo = min(total, self.limite) if (total and self.limite) else (self.limite or total)
                self._fase("lista", alvo or 0, len(self.seguidores))
                if cortou or self._limite_lista_atingido():
                    # cursor fica no início desta página: ao aumentar o limite, a retomada relê e pula os já obtidos
                    self.salvar(ultima_etapa=f"lista: limite de {self.limite} atingido na página {self.est['paginas']}")
                    return
                self.salvar(cursor=pag.proximo, mensagem=f"lista: página {self.est['paginas']} ({len(self.seguidores)} seguidores)",
                            ultima_etapa=f"lista: página {self.est['paginas']}")
                if self.pedido_parada():
                    raise KeyboardInterrupt
                if not pag.proximo:
                    self.est["fim_lista"] = True
                    if self.est.get("lista_limitada"):
                        self.evento("info", "O Instagram informou que exibe só parte da lista de seguidores deste perfil "
                                            "(should_limit_list_of_followers). O restante não é acessível.")
                    self.salvar(ultima_etapa="lista: concluída")

    # ---------- fase 2: perfis em ordem de prioridade

    def _analisar(self, seg: dict) -> dict:
        p = Perfil(usuario=seg["usuario"], pk=seg.get("pk") or "", nome=seg.get("nome") or "", privado=seg.get("privado"),
                   verificado=seg.get("verificado"), etapas=["lista"], triagem=seg.get("triagem") or {})
        modo = self.cfg.get("detalhes", "candidatos")
        pr = (seg.get("triagem") or {}).get("prioridade", triagem.INDEFINIDO)
        ler = triagem.deve_ler(pr, modo, self.cfg_triagem)
        if p.privado:
            self.est["privados"] = self.est.get("privados", 0) + 1
        if ler and self.cliente is not None:
            try:
                self.cliente.detalhes(p)
                self.est["detalhes_lidos"] = self.est.get("detalhes_lidos", 0) + 1
            except (ErroLimite, ErroDesafio, ErroAutenticacao, ErroSemSessao, ErroIndisponivel):
                raise
            except ErroColeta as e:
                p.detalhes, p.erro_detalhes = "indisponivel", str(e)[:200]
                self.est["detalhes_falhos"] = self.est.get("detalhes_falhos", 0) + 1
        elif ler:
            p.detalhes, p.erro_detalhes = "indisponivel", "sem sessão do Instagram para ler a bio"
        else:
            self.est["nao_lidos"] = self.est.get("nao_lidos", 0) + 1
        return {"perfil": p.para_dict(), "classificacao": classificar(p), "em": agora(), "fase": "perfis"}

    def fase_perfis(self):
        pendentes = sorted((s for u, s in self.seguidores.items() if u not in self.analisados),
                           key=lambda s: ((s.get("triagem") or {}).get("prioridade", triagem.INDEFINIDO), self.ordem.get(s["usuario"], 0)))
        if not pendentes:
            return
        total = len(self.seguidores)
        self._fase("perfis", total, len(self.analisados))
        self.salvar(mensagem="perfis: iniciando", ultima_etapa=f"perfis: {len(self.analisados)} de {total}")
        with _abrir_acrescimo(self.pasta / "perfis.jsonl") as arq:
            for seg in pendentes:
                if self.pedido_parada():
                    raise KeyboardInterrupt
                reg = self._analisar(seg)
                _gravar_linha(arq, reg)
                self.analisados.add(seg["usuario"])
                self.est["processados"] = len(self.analisados)
                cls = reg["classificacao"]
                if cls["categorias"]:
                    marc = ", ".join(f"{c['codigo']}:{c['confianca']}" for c in cls["categorias"])
                    self.saida(f"[{self.est['processados']}/{total}] @{seg['usuario']:<30} {cls['situacao']:<12} {marc}")
                if self.est["processados"] % 5 == 0 or self.est["processados"] == total:
                    self._fase("perfis", total, self.est["processados"])
                    self.salvar(mensagem=f"perfis: @{seg['usuario']}",
                                ultima_etapa=f"perfis: {self.est['processados']} de {total}")
        self._fase("perfis", total, len(self.analisados))
        self.salvar(ultima_etapa="perfis: concluída")

    # ---------- fase 3: publicações dos duvidosos

    def alvos_publicacoes(self) -> list[tuple[int, str, dict]]:
        cfgp = self.cfg_triagem["publicacoes"]
        alvos = []
        for u, r in ultimos_registros(self.pasta).items():
            perfil = dict(r["perfil"])
            if not perfil.get("triagem") and u in self.seguidores:
                perfil["triagem"] = self.seguidores[u].get("triagem") or {}
            motivo = precisa_publicacoes(perfil, r["classificacao"], cfgp)
            if motivo:
                alvos.append((motivo[0], motivo[1], r))
        alvos.sort(key=lambda t: (t[0], (t[2]["perfil"].get("triagem") or {}).get("prioridade", 9), self.ordem.get(t[2]["perfil"]["usuario"], 0)))
        return alvos

    def fase_publicacoes(self):
        if self.cfg.get("publicacoes", "duvidosos") == "nenhuma" or self.cliente is None:
            return
        cfgp = self.cfg_triagem["publicacoes"]
        alvos = self.alvos_publicacoes()
        pub = self.est["publicacoes"]
        pub["alvos"] = pub.get("feitos", 0) + len(alvos)
        if not alvos:
            return
        self._fase("publicacoes", pub["alvos"], pub.get("feitos", 0))
        self.salvar(mensagem="publicações: iniciando")
        with _abrir_acrescimo(self.pasta / "perfis.jsonl") as arq:
            for _, motivo, r in alvos:
                if self.pedido_parada():
                    raise KeyboardInterrupt
                p = Perfil.de_dict(r["perfil"])
                if not p.triagem and p.usuario in self.seguidores:
                    p.triagem = self.seguidores[p.usuario].get("triagem") or {}
                try:
                    p.posts = self.cliente.publicacoes(p.usuario, cfgp.get("quantidade", 12))
                    pub["lidas"] = pub.get("lidas", 0) + 1
                except (ErroLimite, ErroDesafio, ErroAutenticacao, ErroSemSessao, ErroIndisponivel):
                    raise
                except ErroColeta as e:
                    p.erro_publicacoes = str(e)[:200]
                    pub["falhas"] = pub.get("falhas", 0) + 1
                p.etapas = list(dict.fromkeys((p.etapas or []) + ["publicacoes"]))
                cls = classificar(p)
                destaques = cfgp.get("destaques", "duvidosos")
                inconclusivo = cls["situacao"] != "identificado"
                if p.pk and (destaques == "sempre" or (destaques == "se_inconclusivo" and inconclusivo)
                             or (destaques == "duvidosos" and inconclusivo and motivo == "classificação duvidosa")):
                    try:
                        p.destaques = self.cliente.destaques(p.pk)
                        pub["destaques"] = pub.get("destaques", 0) + 1
                    except (ErroLimite, ErroDesafio, ErroAutenticacao, ErroSemSessao, ErroIndisponivel):
                        raise
                    except ErroColeta as e:
                        p.erro_publicacoes = (p.erro_publicacoes + f" | destaques: {e}")[:300]
                    p.etapas.append("destaques")
                    cls = classificar(p)
                antes = r["classificacao"]["situacao"]
                _gravar_linha(arq, {"perfil": p.para_dict(), "classificacao": cls, "em": agora(), "fase": "publicacoes",
                                    "motivo_publicacoes": motivo, "situacao_antes": antes})
                pub["feitos"] = pub.get("feitos", 0) + 1
                if cls["situacao"] != antes:
                    pub["mudaram"] = pub.get("mudaram", 0) + 1
                    self.saida(f"  publicações @{p.usuario}: {antes} → {cls['situacao']} "
                               + ", ".join(f"{c['codigo']}:{c['confianca']}" for c in cls["categorias"]))
                self._fase("publicacoes", pub["alvos"], pub["feitos"])
                self.salvar(mensagem=f"publicações: @{p.usuario}", ultima_etapa=f"publicações: {pub['feitos']} de {pub['alvos']}")
        self.salvar(ultima_etapa="publicações: concluída")

    # ---------- laço principal com modo noite

    def _aguardar(self, segundos: int, motivo: str):
        retoma = datetime.fromtimestamp(time.time() + segundos).isoformat(timespec="seconds")
        self.evento("temporario", f"{motivo}; aguardando {segundos // 60} min (retoma ~{retoma[11:16]})")
        self.salvar(status="aguardando", mensagem=f"{motivo}; retoma ~{retoma[11:16]}", retoma_em=retoma)
        self.saida(f"  · {motivo}; aguardando {segundos}s")
        restante = float(segundos)
        while restante > 0:
            if self.pedido_parada():
                raise KeyboardInterrupt
            passo = min(30.0, restante)
            self.dormir(passo)
            restante -= passo
            self.salvar()  # batimento: o painel sabe que o processo continua vivo
        self.est.pop("retoma_em", None)
        self.salvar(status="executando", mensagem="retomando")

    def rodar(self) -> dict:
        if self.est.get("erros"):  # erros de execuções anteriores vão para o histórico
            self.est["erros_anteriores"] = (self.est.get("erros_anteriores", []) + self.est["erros"])[-50:]
            self.est["erros"] = []
        self.est["lista_limitada"] = self.est.get("lista_limitada", False)
        (self.pasta / "parar").unlink(missing_ok=True)
        self.salvar(status="executando", iniciado=self.est.get("iniciado") or agora(), mensagem="iniciando")
        esperas = {"limite": list(config.ESPERAS_NOITE_LIMITE), "rede": list(config.ESPERAS_NOITE_REDE)}
        progresso_na_espera = -1
        status = "concluido"
        while True:
            try:
                self.fase_lista()
                self.fase_perfis()
                self.fase_publicacoes()
                status = "limite_atingido" if (self._limite_lista_atingido() and not self.est.get("fim_lista")) else "concluido"
                break
            except KeyboardInterrupt:
                status = "interrompido"
                (self.pasta / "parar").unlink(missing_ok=True)
                self.evento("info", "interrompido a pedido; use Retomar para continuar")
                break
            except (ErroLimite, ErroIndisponivel) as e:
                tipo = "limite" if isinstance(e, ErroLimite) else "rede"
                feito = len(self.seguidores) + len(self.analisados) + self.est["publicacoes"].get("feitos", 0)
                if progresso_na_espera >= 0 and feito - progresso_na_espera >= 20:
                    esperas = {"limite": list(config.ESPERAS_NOITE_LIMITE), "rede": list(config.ESPERAS_NOITE_REDE)}
                progresso_na_espera = feito
                if self.cfg.get("noite") and esperas[tipo]:
                    try:
                        self._aguardar(esperas[tipo].pop(0), str(e))
                    except KeyboardInterrupt:
                        status = "interrompido"
                        (self.pasta / "parar").unlink(missing_ok=True)
                        break
                    continue  # as fases retomam de onde pararam
                status = e.tipo
                self.evento("temporario", f"{e} — pausado com segurança; retome mais tarde")
                self.saida(f"PAUSADO: {e}")
                break
            except ErroColeta as e:  # desafio, sessão, perfil: precisa de ação humana
                status = e.tipo
                self.evento("intervencao", str(e))
                self.saida(f"PARADO: {e}")
                break
            except Exception as e:  # erro inesperado: preserva o que já foi gravado
                status = "erro"
                self.evento("intervencao", f"{type(e).__name__}: {e}")
                self.saida(f"ERRO: {type(e).__name__}: {e}")
                break
        if self.cliente is not None:
            self.cliente.fechar()
        self.est.pop("retoma_em", None)
        self.est["fase"] = "fim" if status in ("concluido", "limite_atingido") else self.est.get("fase")
        mensagens = {"concluido": "análise concluída (lista acessível até o fim)",
                     "limite_atingido": f"análise concluída para os {self.limite} primeiros seguidores (limite)",
                     "interrompido": "interrompido; use Retomar para continuar"}
        self.salvar(status=status, finalizado=agora(), mensagem=mensagens.get(status, self.est.get("mensagem", "")))
        return self.est


def executar(pasta: Path, cliente=None, saida=print, dormir=time.sleep) -> dict:
    """Roda (ou retoma) a análise. `cliente` é um ClienteInstagram; None cria um com a sessão salva (se houver)."""
    trava = _travar(pasta)
    try:
        return _executar(pasta, cliente, saida, dormir)
    finally:
        trava.unlink(missing_ok=True)


def _executar(pasta: Path, cliente, saida, dormir) -> dict:
    cfg = ler_config(pasta)
    if cliente is None and (cfg.get("fonte") != "arquivo" or cfg.get("detalhes") != "nenhum"):
        from prospeccao import sessao
        from prospeccao.coleta import ClienteInstagram
        try:
            cliente = ClienteInstagram(sessao.carregar() or {}, avisar=lambda m: None)
        except ErroSemSessao as e:
            if cfg.get("fonte") != "arquivo":
                ex = _Execucao(pasta, None, saida, dormir)
                ex.evento("intervencao", str(e))
                ex.salvar(status="sem_sessao", mensagem=str(e))
                saida(f"PARADO: {e}")
                return ex.est
            cliente = None
    ex = _Execucao(pasta, cliente, saida, dormir)
    if cliente is not None:
        cliente.avisar = ex.avisar
        cliente.ritmo.avisar = ex.avisar
    est = ex.rodar()
    try:
        from prospeccao import exportar, revisao
        exportar.exportar(pasta)
        revisao.gerar(pasta)
    except Exception as e:  # exportar nunca deve derrubar a execução já gravada
        saida(f"aviso: exportação falhou ({type(e).__name__}: {e}); rode 'prospeccao exportar'")
    return est


def reclassificar(pasta: Path) -> int:
    """Reaplica as regras atuais aos perfis já coletados (sem acessar a internet). Mantém o histórico de fases."""
    regs = list(iterar_registros(pasta))
    tmp = pasta / "perfis.jsonl.tmp"
    with tmp.open("w", encoding="utf-8") as f:
        for r in regs:
            r["classificacao"] = classificar(Perfil.de_dict(r["perfil"]))
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(pasta / "perfis.jsonl")
    return len({r["perfil"]["usuario"] for r in regs})


def listar() -> list[Path]:
    if not config.RESULTADOS_DIR.exists():
        return []
    return sorted((p for p in config.RESULTADOS_DIR.iterdir() if (p / "config.json").exists()), reverse=True)


def resolver_pasta(ref: str | None) -> Path:
    pastas = listar()
    if not ref or ref == "ultima":
        if not pastas:
            raise SystemExit("Nenhuma análise encontrada em " + str(config.RESULTADOS_DIR))
        return pastas[0]
    p = Path(ref)
    if p.is_dir() and (p / "config.json").exists():
        return p
    p = config.RESULTADOS_DIR / ref
    if p.is_dir():
        return p
    candidatos = [q for q in pastas if ref.lstrip("@").lower() in q.name.lower()]
    if not candidatos:
        raise SystemExit(f"Análise não encontrada: {ref}")
    return candidatos[0]
