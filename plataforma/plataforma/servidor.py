"""Servidor local da plataforma (só 127.0.0.1): interface web + API JSON.

Segurança: atende só 127.0.0.1; recusa Host estranho (DNS rebinding) e ações vindas de outros sites (CSRF: exige
Origin/Referer da própria plataforma e corpo JSON); downloads só de uma lista fixa de arquivos dentro das pastas de
resultados; a sessão do Instagram nunca sai do módulo `prospeccao.sessao` (criptografada, fora do projeto).
"""

import json
import logging
import mimetypes
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from plataforma import acoes, base, claude, config, consultas, db, exportar, sincronizar

WEB = Path(__file__).resolve().parent / "web"
log = logging.getLogger("plataforma")
_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


class ErroHTTP(Exception):
    def __init__(self, codigo: int, mensagem: str):
        super().__init__(mensagem)
        self.codigo = codigo


def _um(q: dict) -> dict:
    return {k: v[-1] for k, v in q.items() if v}


def _bool(v) -> bool:
    return v in (True, 1, "1", "true", "sim", "on")


# ----------------------------------------------------------------------------------------- rotas

def _execucao_ou_404(eid: str) -> dict:
    d = consultas.detalhe_execucao(eid)
    if not d:
        raise ErroHTTP(404, "Execução não encontrada.")
    return d


_searx_cache = [0.0, False]


def _sistema() -> dict:
    import httpx

    from empresas import config as emp_config
    from prospeccao import sessao
    exe = claude.localizar()
    # verificação própria (a da ferramenta guarda o 1º resultado até o processo terminar), com cache de 60 s
    agora = time.time()
    if agora - _searx_cache[0] > 60:
        try:
            ok = httpx.get(f"{emp_config.SEARXNG_URL}/healthz", timeout=1).status_code == 200
        except httpx.HTTPError:
            ok = False
        _searx_cache[:] = [agora, ok]
    searx = _searx_cache[1]
    con = db.conexao()
    return {
        "sessao_instagram": sessao.descricao(),
        "searxng": {"disponivel": bool(searx), "url": emp_config.SEARXNG_URL},
        "claude": {"disponivel": bool(exe), "caminho": str(exe) if exe else ""},
        "pastas": {"instagram": str(config.resultados_instagram()), "empresas": str(config.resultados_empresas()),
                   "banco": str(config.db_arquivo()), "claude": str(config.CLAUDE_DIR)},
        "parametros": {"dias_desatualizada": config.DIAS_DESATUALIZADA, "dias_repesquisa": config.DIAS_REPESQUISA,
                       "max_linhas_lote": config.MAX_LINHAS_LOTE},
        "contagens": {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("execucoes", "empresas", "pesquisas", "perfis", "vinculos", "duplicidades")},
        "historico": [dict(r) for r in con.execute("SELECT em, tipo, descricao FROM historico ORDER BY id DESC LIMIT 30")],
    }


def _sessao(acao: str, dados: dict) -> dict:
    from prospeccao import sessao
    if acao == "firefox":
        sessao.salvar(sessao.importar_firefox(), "importada do Firefox")
        return {"mensagem": "Sessão importada do Firefox. Use 'Testar' para conferir."}
    if acao == "definir":
        sessao.salvar(sessao.de_sessionid(str(dados.get("sessionid") or "")), "colada na plataforma")
        return {"mensagem": "Sessão salva. Use 'Testar' para conferir."}
    if acao == "remover":
        sessao.remover()
        return {"mensagem": "Sessão removida deste computador."}
    if acao == "testar":
        from prospeccao.coleta import ClienteInstagram, ErroColeta
        c = ClienteInstagram(sessao.carregar() or {}, avisar=lambda m: None)
        try:
            return {"mensagem": f"Sessão válida: logado como @{c.conta_logada()['usuario']}", "ok": True}
        except ErroColeta as e:
            return {"mensagem": f"Sessão não validada: {e}", "ok": False}
        finally:
            c.fechar()
    raise ErroHTTP(404, "Ação desconhecida.")


def _log(eid: str, linhas: int = 200) -> dict:
    achado = sincronizar.pasta_da_execucao(eid)
    if not achado:
        raise ErroHTTP(404, "Execução não encontrada.")
    arq = achado[1] / "log.txt"
    if not arq.is_file():
        return {"linhas": []}
    with arq.open("rb") as f:
        f.seek(0, 2)
        tam = f.tell()
        f.seek(max(0, tam - 200_000))
        texto = f.read().decode("utf-8", errors="replace")
    return {"linhas": texto.splitlines()[-linhas:]}


def rota_get(caminho: str, q: dict):
    """Devolve (codigo, dados) ou (codigo, bytes, tipo, extra) para arquivos."""
    partes = [unquote(p) for p in caminho.strip("/").split("/")][1:]  # sem o "api"
    if partes == ["status"]:
        con = db.conexao()
        return {"em_andamento": con.execute("SELECT COUNT(*) FROM execucoes WHERE em_andamento=1").fetchone()[0],
                "pendencias": consultas.pendencias_resumo(), "agora": base.agora()}
    if partes == ["visao-geral"]:
        return consultas.visao_geral()
    if partes == ["segmentos"]:
        return consultas.segmentos()
    if partes == ["pendencias"]:
        return consultas.pendencias()
    if partes == ["sistema"]:
        return _sistema()
    if partes == ["execucoes"]:
        return consultas.listar_execucoes(q)
    if len(partes) >= 2 and partes[0] == "execucoes":
        eid = partes[1]
        if len(partes) == 2:
            return _execucao_ou_404(eid)
        sub = partes[2]
        if sub == "perfis":
            return consultas.listar_perfis(q | {"execucao": eid})
        if sub == "pesquisas":
            return consultas.itens_execucao_empresas(eid, q)
        if sub == "candidatos":
            try:
                return acoes.candidatos_da_execucao(eid, q.get("escopo") or "identificados",
                                                    [s for s in (q.get("segmentos") or "").split(",") if s],
                                                    _bool(q.get("incluir")), q.get("dias") or None)
            except acoes.AcaoInvalida as e:
                raise ErroHTTP(400, str(e)) from None
        if sub == "log":
            return _log(eid)
        if sub == "pedido-claude":
            try:
                return {"texto": claude.pedido_chat(eid, int(q["max"]) if q.get("max") else None)}
            except ValueError as e:
                raise ErroHTTP(400, str(e)) from None
        if sub == "arquivo" and len(partes) >= 4:
            d = _execucao_ou_404(eid)
            rel = "/".join(partes[3:])
            permitidos = {a["arquivo"] for a in d["arquivos"]}
            alvo = (Path(d["pasta"]) / rel).resolve()
            if rel not in permitidos or Path(d["pasta"]).resolve() not in alvo.parents or not alvo.is_file():
                raise ErroHTTP(404, "Arquivo não encontrado.")
            tipo = {".csv": "text/csv; charset=utf-8", ".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8",
                    ".json": "application/json; charset=utf-8", ".jsonl": "text/plain; charset=utf-8",
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}.get(alvo.suffix, "application/octet-stream")
            disp = "inline" if alvo.suffix in (".md", ".txt", ".json", ".jsonl") else "attachment"
            return 200, alvo.read_bytes(), tipo, {"Content-Disposition": f"{disp}; filename=\"{quote(d['nome'] + '_' + alvo.name)}\""}
    if partes == ["empresas"]:
        return consultas.listar_empresas(q)
    if partes == ["empresas", "opcoes"]:
        return consultas.opcoes_empresas()
    if partes == ["empresas", "exportar.csv"]:
        return 200, exportar.csv_bytes(q), "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="empresas.csv"'}
    if partes == ["empresas", "exportar.xlsx"]:
        return (200, exportar.xlsx_bytes(q), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                {"Content-Disposition": 'attachment; filename="empresas.xlsx"'})
    if len(partes) == 2 and partes[0] == "empresas":
        try:
            d = consultas.detalhe_empresa(int(partes[1]))
        except ValueError:
            d = None
        if not d:
            raise ErroHTTP(404, "Empresa não encontrada.")
        return d
    if partes == ["fila"]:
        from plataforma import fila
        try:
            return {"itens": fila.listar(q.get("estado") or "pendente",
                                         [s for s in (q.get("segmentos") or "").split(",") if s],
                                         q.get("execucao") or "", q.get("limite") or None),
                    "resumo": fila.resumo(), "segmentos": consultas.segmentos()}
        except ValueError as e:
            raise ErroHTTP(400, str(e)) from None
    if partes == ["perfis"]:
        return consultas.listar_perfis(q)
    if len(partes) == 2 and partes[0] == "perfis":
        d = consultas.detalhe_perfil(partes[1].lstrip("@").lower())
        if not d:
            raise ErroHTTP(404, "Perfil não encontrado.")
        return d
    raise ErroHTTP(404, "Rota não encontrada.")


def rota_post(caminho: str, dados: dict):
    partes = [unquote(p) for p in caminho.strip("/").split("/")][1:]
    try:
        if partes == ["instagram", "analisar"]:
            return {"id": acoes.iniciar_instagram(dados)}
        if partes == ["empresas", "pesquisar"]:
            return {"id": acoes.iniciar_empresas(str(dados.get("lista") or ""), str(dados.get("nome") or ""))}
        if partes == ["fila", "pesquisar"]:
            return {"id": acoes.pesquisar_fila(dados.get("limite"), dados.get("segmentos") or None,
                                               _bool(dados.get("incluir_pesquisadas")), dados.get("dias"))}
        if partes == ["fila", "dispensar"]:
            from plataforma import fila
            return {"n": fila.marcar([str(u) for u in (dados.get("usuarios") or [])], "dispensado",
                                     motivo=str(dados.get("motivo") or "dispensado na plataforma"))}
        if partes == ["fila", "reabrir"]:
            from plataforma import fila
            return {"n": fila.marcar([str(u) for u in (dados.get("usuarios") or [])], "pendente")}
        if partes == ["empresas", "atualizar"]:
            ids = dados.get("ids") or (consultas.ids_empresas(dados.get("filtros") or {}, config.MAX_LINHAS_LOTE)
                                       if dados.get("filtros") is not None else [])
            return {"id": acoes.atualizar_empresas([int(i) for i in ids])}
        if partes == ["perfis", "pesquisar-empresas"]:
            usuarios = dados.get("usuarios")
            if usuarios is None:
                filtros = dict(dados.get("filtros") or {}) | {"por_pagina": 500, "pagina": 1}
                usuarios = [p["usuario"] for p in consultas.listar_perfis(filtros)["itens"]]
            return {"id": acoes.pesquisar_empresas_de_perfis([str(u) for u in usuarios], _bool(dados.get("incluir_pesquisadas")))}
        if len(partes) == 3 and partes[0] == "empresas" and partes[2] == "vincular":
            with db.transacao() as c:
                base.decidir_vinculo(c, str(dados.get("usuario") or ""), int(partes[1]), str(dados.get("estado") or "confirmado"),
                                     str(dados.get("nota") or ""))
            return {"ok": True}
        if partes == ["duplicidades"]:
            with db.transacao() as c:
                base.decidir_duplicidade(c, int(dados["a"]), int(dados["b"]), str(dados.get("decisao")),
                                         int(dados["manter"]) if dados.get("manter") else None, str(dados.get("nota") or ""))
            return {"ok": True}
        if len(partes) == 3 and partes[0] == "pesquisas" and partes[2] == "separar":
            with db.transacao() as c:
                return {"empresa_id": base.separar(c, partes[1], str(dados.get("nota") or ""))}
        if len(partes) == 3 and partes[0] == "execucoes":
            eid, acao = partes[1], partes[2]
            if acao == "retomar":
                return {"id": acoes.retomar(eid, dados)}
            if acao == "parar":
                return {"id": acoes.parar(eid)}
            if acao == "arquivar":
                sincronizar.arquivar(eid, _bool(dados.get("arquivada", True)))
                return {"ok": True}
            if acao == "pesquisar-empresas":
                return {"id": acoes.pesquisar_empresas_da_execucao(
                    eid, str(dados.get("escopo") or "identificados"), dados.get("segmentos") or None,
                    _bool(dados.get("incluir_pesquisadas")), dados.get("dias"))}
            if acao == "claude":
                return {"id": claude.iniciar(eid, dados.get("max_itens"))}
        if len(partes) == 2 and partes[0] == "sessao":
            return _sessao(partes[1], dados)
        if partes == ["sincronizar"]:
            return sincronizar.sincronizar(forcar=_bool(dados.get("completa")))
    except (acoes.AcaoInvalida, ValueError, KeyError) as e:
        raise ErroHTTP(400, str(e) or "Dados inválidos.") from None
    raise ErroHTTP(404, "Rota não encontrada.")


# ----------------------------------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    porta = config.PORTA
    server_version = "Plataforma"
    sys_version = ""

    def log_message(self, *a):
        pass

    def _enviar(self, codigo: int, corpo, tipo="application/json; charset=utf-8", extra=None):
        if not isinstance(corpo, bytes):
            corpo = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", _CSP)
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _hosts(self):
        return (f"127.0.0.1:{self.porta}", f"localhost:{self.porta}")

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in self._hosts()

    def _origem_ok(self) -> bool:
        o = self.headers.get("Origin") or self.headers.get("Referer") or ""
        return urlparse(o).netloc in self._hosts()

    def _erro(self, e: Exception):
        if isinstance(e, ErroHTTP):
            return self._enviar(e.codigo, {"erro": str(e)})
        log.error("Erro em %s %s: %s", self.command, self.path, traceback.format_exc())
        self._enviar(500, {"erro": f"Erro interno ({type(e).__name__}). Detalhes em {config.DADOS_DIR / 'plataforma.log'}"})

    def do_GET(self):
        if not self._host_ok():
            return self._enviar(403, {"erro": "Acesso negado"})
        url = urlparse(self.path)
        caminho = url.path
        try:
            if caminho.startswith("/api/"):
                r = rota_get(caminho, _um(parse_qs(url.query)))
                if isinstance(r, tuple):
                    return self._enviar(r[0], r[1], r[2], r[3])
                return self._enviar(200, r)
            nome = "index.html" if caminho in ("/", "/index.html") else caminho.removeprefix("/static/")
            alvo = (WEB / nome).resolve()
            if caminho != "/" and not caminho.startswith("/static/") or WEB.resolve() not in alvo.parents or not alvo.is_file():
                return self._enviar(404, {"erro": "Não encontrado"})
            tipo = mimetypes.guess_type(alvo.name)[0] or "application/octet-stream"
            if tipo.startswith("text/") or tipo in ("application/javascript",):
                tipo += "; charset=utf-8"
            self._enviar(200, alvo.read_bytes(), tipo)
        except (ValueError, KeyError) as e:  # parâmetro inválido na URL (data, número...)
            self._enviar(400, {"erro": f"Parâmetro inválido: {e}"})
        except Exception as e:
            self._erro(e)

    def do_POST(self):
        if not self._host_ok() or not self._origem_ok():
            return self._enviar(403, {"erro": "Acesso negado"})
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._enviar(415, {"erro": "Envie JSON"})
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho > 2_000_000:
                raise ErroHTTP(413, "Conteúdo grande demais.")
            bruto = self.rfile.read(tamanho) if tamanho else b"{}"
            try:
                dados = json.loads(bruto.decode("utf-8") or "{}")
            except ValueError:
                raise ErroHTTP(400, "JSON inválido.") from None
            if not isinstance(dados, dict):
                raise ErroHTTP(400, "JSON inválido.")
            self._enviar(200, rota_post(urlparse(self.path).path, dados))
        except Exception as e:
            self._erro(e)


def _sincronizador(parar: threading.Event):
    while not parar.wait(config.INTERVALO_SINCRONIA_S):
        try:
            sincronizar.sincronizar()
        except Exception:
            log.exception("Falha na sincronização")


def configurar_log():
    config.DADOS_DIR.mkdir(parents=True, exist_ok=True)
    h = logging.FileHandler(config.DADOS_DIR / "plataforma.log", encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(h)
    log.setLevel(logging.INFO)


def servir(porta: int = config.PORTA, abrir: bool = True):
    configurar_log()
    Handler.porta = porta
    t = time.time()
    r = sincronizar.sincronizar()
    print(f"Base sincronizada em {time.time() - t:.1f}s ({r or 'sem mudanças'}). Banco: {config.db_arquivo()}")
    parar = threading.Event()
    threading.Thread(target=_sincronizador, args=(parar,), daemon=True).start()
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Handler)
    url = f"http://127.0.0.1:{porta}/"
    print(f"Plataforma em {url}  (Ctrl+C para encerrar; as execuções em andamento continuam)")
    log.info("Plataforma iniciada em %s", url)
    if abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        parar.set()
        servidor.server_close()
