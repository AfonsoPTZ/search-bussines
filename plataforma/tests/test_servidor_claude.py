"""Servidor HTTP de verdade (porta livre em 127.0.0.1): rotas, segurança, downloads e exportação. Revisão pelo Claude com
um processo simulado que imprime o mesmo formato stream-json do Claude Code."""

import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from plataforma import claude, servidor, sincronizar
from tests.conftest import Ambiente, perfil

R = Ambiente.registro


@pytest.fixture
def srv(amb):
    amb.lote("2026-10-18_100000_lote", [
        R(1, "Funerária Teste | Curitiba/PR", {"cnpj": [("11.222.333/0001-81", "site", True)], "uf": [("PR", "cadastro", True)]}),
        R(2, "Floricultura Teste | Curitiba/PR", {"telefones": [("(41) 3333-3333", "busca", False)]}),
    ])
    (amb.raiz / "emp" / "2026-10-18_100000_lote" / "empresas.csv").write_bytes(b"a;b\n")
    (amb.raiz / "emp" / "2026-10-18_100000_lote" / "segredo.txt").write_text("não pode sair", encoding="utf-8")
    amb.analise("origem_teste", [perfil("teste_flores", "Flores Teste", "Floricultura e coroas de flores para velórios")])
    sincronizar.sincronizar()
    h = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Handler)
    servidor.Handler.porta = h.server_address[1]
    threading.Thread(target=h.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{h.server_address[1]}"
    h.shutdown()
    h.server_close()


def req(url, metodo="GET", dados=None, cab=None):
    base = url.split("/api")[0].split("/static")[0].rstrip("/")
    cabecalhos = {"Host": base.split("//")[1]} | (cab or {})
    corpo = None
    if dados is not None:
        corpo = json.dumps(dados).encode()
        cabecalhos.setdefault("Content-Type", "application/json")
        cabecalhos.setdefault("Origin", base)
    r = urllib.request.Request(url, data=corpo, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def jget(srv, caminho):
    c, corpo, _ = req(srv + caminho)
    assert c == 200, (caminho, corpo)
    return json.loads(corpo)


def test_paginas_e_rotas_principais(srv):
    c, corpo, cab = req(srv + "/")
    assert c == 200 and b"/static/app.js" in corpo and "frame-ancestors 'none'" in cab["Content-Security-Policy"]
    assert req(srv + "/static/app.js")[0] == 200
    assert req(srv + "/static/../servidor.py")[0] == 404
    vg = jget(srv, "/api/visao-geral")
    assert vg["empresas"]["total"] == 2 and vg["perfis"]["identificados"] == 1
    assert jget(srv, "/api/empresas?uf=PR")["total"] == 2  # a pista "Curitiba/PR" da entrada vale como UF
    assert jget(srv, "/api/empresas?uf=SP")["total"] == 0
    assert jget(srv, "/api/status")["em_andamento"] == 0
    e = jget(srv, "/api/empresas")["itens"][0]
    assert jget(srv, f"/api/empresas/{e['id']}")["empresa"]["id"] == e["id"]
    assert req(srv + "/api/empresas/99999")[0] == 404
    assert req(srv + "/api/empresas/abc")[0] == 404
    assert jget(srv, "/api/perfis/teste_flores")["perfil"]["usuario"] == "teste_flores"
    assert jget(srv, "/api/execucoes/emp:2026-10-18_100000_lote")["tipo"] == "empresas"
    assert len(jget(srv, "/api/execucoes/emp:2026-10-18_100000_lote/pesquisas")["itens"]) == 2
    assert jget(srv, "/api/pendencias")["resumo"]["perfis_sem_pesquisa"] == 1
    assert req(srv + "/api/nao-existe")[0] == 404


def test_seguranca(srv):
    assert req(srv + "/api/status", cab={"Host": "evil.example:80"})[0] == 403          # DNS rebinding
    assert req(srv + "/api/sincronizar", "POST", {}, {"Origin": "http://evil.example"})[0] == 403  # CSRF
    c, _, _ = req(srv + "/api/sincronizar", "POST", {}, {"Content-Type": "application/x-www-form-urlencoded"})
    assert c == 415
    c, corpo, _ = req(srv + "/api/empresas/pesquisar", "POST", {"lista": ""})
    assert c == 400 and "Informe" in json.loads(corpo)["erro"]
    assert req(srv + "/api/sincronizar", "POST", {})[0] == 200


def test_downloads_so_da_lista_permitida(srv):
    c, corpo, cab = req(srv + "/api/execucoes/emp:2026-10-18_100000_lote/arquivo/empresas.csv")
    assert c == 200 and corpo == b"a;b\n" and "attachment" in cab["Content-Disposition"]
    assert req(srv + "/api/execucoes/emp:2026-10-18_100000_lote/arquivo/segredo.txt")[0] == 404
    assert req(srv + "/api/execucoes/emp:2026-10-18_100000_lote/arquivo/..%2F..%2Fsegredo.txt")[0] == 404
    assert req(srv + "/api/execucoes/emp:..%2F..%2Fx/arquivo/empresas.csv")[0] == 404


def test_exportacao_respeita_filtros_e_marca_nao_confirmados(srv):
    c, corpo, cab = req(srv + "/api/empresas/exportar.csv?q=floricultura")
    texto = corpo.decode("utf-8-sig")
    assert c == 200 and "Floricultura Teste" in texto and "Funerária Teste" not in texto
    assert "(41) 3333-3333 (não confirmado)" in texto
    c, corpo, _ = req(srv + "/api/empresas/exportar.xlsx")
    assert c == 200 and corpo[:2] == b"PK"


def test_acoes_pela_api(srv, amb):
    eid = jget(srv, "/api/empresas?q=floricultura")["itens"][0]["id"]
    c, corpo, _ = req(srv + f"/api/empresas/{eid}/vincular", "POST", {"usuario": "@teste_flores", "estado": "confirmado"})
    assert c == 200
    assert jget(srv, f"/api/empresas/{eid}")["empresa"]["segmentos_perfil"] == ["D"]
    c, corpo, _ = req(srv + "/api/empresas/pesquisar", "POST", {"lista": "Padaria Teste | Bauru/SP", "nome": "x"})
    assert c == 200 and json.loads(corpo)["id"].startswith("emp:") and amb.processos
    c, corpo, _ = req(srv + "/api/perfis/pesquisar-empresas", "POST", {"usuarios": ["teste_flores"]})
    assert c == 400 and "já pesquisados" in json.loads(corpo)["erro"]  # vinculada acima a uma empresa recente


# ------------------------------------------------------------------ revisão pelo Claude

_FALSO = r'''
import json, sys
print(json.dumps({"type": "system", "subtype": "init"}))
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "\"C:/x/empresas.exe\" revisar \"lote\""}}]}}))
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch", "input": {"query": "Floricultura Teste CNPJ"}}]}}))
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Revisei 1 item."}]}}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "1 item revisado; 1 incerto.", "num_turns": 4}))
'''


def test_revisao_pelo_claude_prepara_pedido_restrito_e_registra_o_andamento(srv, amb, monkeypatch, tmp_path):
    exe = tmp_path / "claude.exe"
    exe.write_text("falso")
    monkeypatch.setenv("PLATAFORMA_CLAUDE", str(exe))
    alvo = "emp:2026-10-18_100000_lote"
    assert "/pesquisa-empresas" in claude.pedido_chat(alvo) and "2026-10-18_100000_lote" in claude.pedido_chat(alvo)
    pasta = claude.preparar(alvo, 3)
    cfg = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    assert cfg["ferramentas"][-3:] == ["WebSearch", "WebFetch", "Skill"] and "no máximo 3 itens" in cfg["prompt"]
    regras = cfg["ferramentas"][:-3]
    assert all(r.startswith("Bash(") and "empresas.exe" in r for r in regras)
    assert not any(r.startswith("Bash(*") for r in regras)  # prefixo exato: só revisar/corrigir/exportar
    assert {r.split()[-1] for r in regras} == {"revisar:*)", "corrigir:*)", "exportar:*)"}
    script = tmp_path / "falso.py"
    script.write_text(_FALSO, encoding="utf-8")
    assert claude.executar(pasta, [sys.executable, str(script)]) == 0
    est = json.loads((pasta / "estado.json").read_text(encoding="utf-8"))
    assert est["status"] == "concluido" and est["comandos"] == 2 and est["turnos"] == 4
    assert "empresas revisar" in (pasta / "log.txt").read_text(encoding="utf-8")
    sincronizar.sincronizar()
    x = jget(srv, "/api/execucoes/claude:" + pasta.name)
    assert x["estado"] == "concluida" and x["origem_execucao"] == alvo
    assert any(f["tipo"] == "revisao_claude" for f in jget(srv, "/api/execucoes/" + alvo)["filhas"])


def test_revisao_do_instagram_so_permite_a_ferramenta_e_falha_sem_resultado(amb, monkeypatch, tmp_path):
    exe = tmp_path / "claude.exe"
    exe.write_text("falso")
    monkeypatch.setenv("PLATAFORMA_CLAUDE", str(exe))
    amb.analise("origem_teste", [perfil("teste_flores", "Flores", "floricultura")])
    sincronizar.sincronizar()
    eid = "ig:" + sincronizar.pastas_instagram()[0].name
    pasta = claude.preparar(eid)
    cfg = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    assert cfg["ferramentas"][-1] == "Skill" and all("prospeccao.exe" in r for r in cfg["ferramentas"][:-1]) and "--revisor claude" in cfg["prompt"]
    assert claude.executar(pasta, [sys.executable, "-c", "print('sem json')"]) == 1
    assert json.loads((pasta / "estado.json").read_text(encoding="utf-8"))["status"] == "falhou"
    with pytest.raises(ValueError):
        claude.preparar("ig:nao-existe")


def test_sem_claude_instalado_a_mensagem_orienta_copiar_o_pedido(amb, monkeypatch, tmp_path):
    monkeypatch.setenv("PLATAFORMA_CLAUDE", str(tmp_path / "nao-existe.exe"))
    amb.lote("2026-10-18_100000_lote", [R(1, "Padaria Teste | Bauru/SP")])
    sincronizar.sincronizar()
    with pytest.raises(ValueError, match="Copiar pedido"):
        claude.preparar("emp:2026-10-18_100000_lote")
