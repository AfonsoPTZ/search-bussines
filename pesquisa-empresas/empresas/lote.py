"""Execução em lote com checkpoint: cada empresa concluída é gravada em registros.jsonl na hora.

Estrutura de um lote (resultados/<data>_<nome>/):
    entrada.<ext>      cópia da lista original
    registros.jsonl    um registro por empresa (fonte da verdade; permite retomar)
    correcoes.jsonl    histórico das correções feitas na revisão
    progresso.json     andamento (lido pelo painel e pelo comando status)
    empresas.xlsx / empresas.csv / fontes.csv   exportações
"""

import json
import os
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from empresas import config, entradas
from empresas.pesquisa import pesquisar


def _slug(texto: str) -> str:
    from empresas.util import sem_acentos
    return re.sub(r"[^a-z0-9]+", "-", sem_acentos(texto).lower()).strip("-")[:40] or "lote"


def criar(arquivo: Path, nome: str | None = None) -> Path:
    pasta = config.RESULTADOS_DIR / f"{datetime.now():%Y-%m-%d_%H%M%S}_{_slug(nome or arquivo.stem)}"
    pasta.mkdir(parents=True, exist_ok=False)
    shutil.copy(arquivo, pasta / f"entrada{arquivo.suffix.lower() or '.txt'}")
    return pasta


def arquivo_entrada(pasta: Path) -> Path:
    return next(pasta.glob("entrada.*"))


def ler_registros(pasta: Path) -> dict[int, dict]:
    """Último registro de cada linha (o arquivo é só de acréscimo)."""
    regs = {}
    caminho = pasta / "registros.jsonl"
    if caminho.exists():
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                try:
                    d = json.loads(linha)
                except json.JSONDecodeError:
                    continue  # linha truncada por interrupção
                regs[d["linha"]] = d
    return regs


def substituir(tmp: Path, destino: Path, tentativas: int = 40):
    """Troca atômica com novas tentativas: no Windows, quem está lendo o arquivo (painel, plataforma) impede a troca
    por alguns milissegundos (PermissionError)."""
    for i in range(tentativas):
        try:
            tmp.replace(destino)
            return
        except PermissionError:
            if i == tentativas - 1:
                raise
            time.sleep(0.05 * (1 + i % 5))


def regravar_registros(pasta: Path, regs: dict[int, dict]):
    tmp = pasta / "registros.jsonl.tmp"
    with tmp.open("w", encoding="utf-8") as f:
        for k in sorted(regs):
            f.write(json.dumps(regs[k], ensure_ascii=False) + "\n")
    substituir(tmp, pasta / "registros.jsonl")


def ultimo_lote() -> Path | None:
    if not config.RESULTADOS_DIR.exists():
        return None
    pastas = sorted(p for p in config.RESULTADOS_DIR.iterdir() if p.is_dir() and any(p.glob("entrada.*")))
    return pastas[-1] if pastas else None


def resolver_pasta(ref: str | None) -> Path:
    if not ref or ref == "ultimo":
        p = ultimo_lote()
        if not p:
            raise SystemExit("Nenhum lote encontrado em " + str(config.RESULTADOS_DIR))
        return p
    p = Path(ref)
    if not p.exists():
        p = config.RESULTADOS_DIR / ref
    if not p.exists():
        candidatos = sorted(config.RESULTADOS_DIR.glob(f"*{ref}*"))
        if not candidatos:
            raise SystemExit(f"Lote não encontrado: {ref}")
        p = candidatos[-1]
    return p


def _gravar_progresso(pasta: Path, dados: dict):
    tmp = pasta / "progresso.json.tmp"
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    substituir(tmp, pasta / "progresso.json")


def pid_vivo(pid) -> bool:
    """O processo ainda existe? (sem enviar sinal: no Windows, os.kill(pid, 0) interromperia o processo)"""
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


class LoteEmUso(RuntimeError):
    pass


def _travar(pasta: Path) -> Path:
    """Um só processo por lote: dois 'retomar' seguidos não pesquisam (nem gravam) em dobro."""
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
                raise LoteEmUso(f"O lote já está sendo pesquisado por outro processo (pid {dono}).")
            trava.unlink(missing_ok=True)  # trava de um processo que morreu
    raise LoteEmUso("Não foi possível reservar o lote; tente de novo.")


BATIMENTO_S = 20  # o progresso é regravado a cada N s: quem lê sabe que o processo continua vivo


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def pedir_parada(pasta: Path):
    """Pede para o lote parar com segurança: as empresas em andamento terminam, as demais ficam pendentes."""
    (pasta / "parar").touch()


def executar(pasta: Path, workers: int = config.WORKERS_PADRAO, refazer_erros: bool = True, saida=print) -> dict:
    trava = _travar(pasta)
    try:
        return _executar(pasta, workers, refazer_erros, saida)
    finally:
        trava.unlink(missing_ok=True)


def _executar(pasta: Path, workers: int, refazer_erros: bool, saida) -> dict:
    lista = entradas.ler(arquivo_entrada(pasta))
    feitos = ler_registros(pasta)
    pendentes = [e for e in lista if e.linha not in feitos or (refazer_erros and feitos[e.linha]["status"] == "erro")]
    total = len(lista)
    inicio = time.time()
    (pasta / "parar").unlink(missing_ok=True)
    progresso = {
        "pasta": str(pasta), "total": total, "concluidas": total - len(pendentes), "em_andamento": [],
        "iniciado": _agora(), "finalizado": None, "status": "executando", "pid": os.getpid(), "atualizado": _agora(),
    }
    _gravar_progresso(pasta, progresso)
    if pendentes and total - len(pendentes):
        saida(f"Retomando: {total - len(pendentes)} já concluídas, {len(pendentes)} pendentes.")
    lock = threading.Lock()
    fim = threading.Event()

    def gravar():  # sempre com o lock; o progresso é informativo: uma falha ao gravá-lo não para a pesquisa
        progresso["atualizado"] = _agora()
        try:
            _gravar_progresso(pasta, progresso)
        except OSError as e:
            saida(f"aviso: progresso não gravado agora ({type(e).__name__}); segue na próxima atualização")

    def batimento():
        while not fim.wait(BATIMENTO_S):
            try:
                with lock:
                    gravar()
            except Exception:  # o batimento nunca morre em silêncio por um erro passageiro
                pass

    def tarefa(e):
        with lock:
            progresso["em_andamento"].append(e.original)
            gravar()
        try:
            return e, pesquisar(e)
        finally:
            with lock:
                progresso["em_andamento"].remove(e.original)

    threading.Thread(target=batimento, daemon=True).start()
    status = "concluido"
    parando = False
    try:
        with open(pasta / "registros.jsonl", "a", encoding="utf-8") as arq, ThreadPoolExecutor(max(1, workers)) as ex:
            futuros = [ex.submit(tarefa, e) for e in pendentes]
            try:
                for fut in as_completed(futuros):
                    if fut.cancelled():
                        continue
                    e, reg = fut.result()
                    with lock:
                        arq.write(json.dumps(reg, ensure_ascii=False) + "\n")
                        arq.flush()
                        progresso["concluidas"] += 1
                        gravar()
                        n = progresso["concluidas"]
                    campos = reg["campos"]
                    cnpj = campos.get("cnpj", [{}])[0].get("valor", "-") if campos.get("cnpj") else "-"
                    saida(f"[{n}/{total}] {e.original[:50]:<50} {reg['status']:<14} {reg['confianca']:<6} CNPJ {cnpj}")
                    if not parando and (pasta / "parar").exists():
                        # parada segura: as que não começaram são canceladas; as em andamento terminam e são gravadas
                        parando = True
                        for f in futuros:
                            f.cancel()
                        saida("Parada pedida: terminando as empresas em andamento.")
            except KeyboardInterrupt:  # Ctrl+C: as em andamento são refeitas no 'retomar'
                parando = True
                for f in futuros:
                    f.cancel()
            except BaseException:  # falha inesperada (disco, permissão...): para tudo e marca erro, sem fingir conclusão
                status = "erro"
                for f in futuros:
                    f.cancel()
                raise
            if parando and any(f.cancelled() for f in futuros):
                status = "interrompido"
                saida("Interrompido: as empresas pendentes continuam com 'retomar'.")
    finally:
        fim.set()
        (pasta / "parar").unlink(missing_ok=True)
        with lock:
            registros = ler_registros(pasta)
            progresso["concluidas"] = sum(1 for e in lista if e.linha in registros)
            erros = sum(1 for e in lista if e.linha in registros and registros[e.linha]["status"] == "erro")
            if status == "concluido" and erros:
                status = "concluido_com_erros"
            if status == "concluido" and progresso["concluidas"] < total:
                status = "interrompido"  # nunca declarar concluído com empresas faltando
            progresso.update(status=status, finalizado=_agora(), duracao_s=round(time.time() - inicio),
                             em_andamento=[], erros=erros)
            gravar()
    return progresso
