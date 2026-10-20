"""Coletor contra um Instagram SIMULADO (httpx.MockTransport). Nenhuma requisição real; dados são DE TESTE FICTÍCIOS."""

import json

import httpx
import pytest

from prospeccao.coleta import (ClienteInstagram, ErroAutenticacao, ErroDesafio, ErroIndisponivel, ErroLimite,
                               ErroPerfil, ErroSemSessao, Ritmo, ler_lista_arquivo)
from prospeccao.perfis import Perfil

SESSAO_TESTE = {"sessionid": "123%3ATESTE%3Afalso-valor-de-teste", "ds_user_id": "123", "csrftoken": "csrf-teste"}


class Relogio:
    def __init__(self):
        self.t, self.dormiu = 1000.0, []

    def agora(self):
        return self.t

    def dormir(self, s):
        self.dormiu.append(s)
        self.t += s


def cliente(handler, esperas=(1, 2)):
    rel = Relogio()
    c = ClienteInstagram(dict(SESSAO_TESTE), transporte=httpx.MockTransport(handler),
                         ritmo=Ritmo(dormir=rel.dormir, agora=rel.agora, pausa_a_cada=0),
                         esperas_limite=list(esperas), avisar=lambda m: None)
    return c, rel


def usuarios(ini, fim):
    return [{"pk": str(i), "username": f"teste_seguidor_{i}", "full_name": f"Teste {i}", "is_private": False} for i in range(ini, fim)]


def test_sem_sessao():
    with pytest.raises(ErroSemSessao):
        ClienteInstagram({})


def test_paginacao_e_cabecalhos():
    vistos = []

    def h(req: httpx.Request):
        vistos.append(req)
        mx = req.url.params.get("max_id")
        if mx is None:
            return httpx.Response(200, json={"users": usuarios(0, 3), "next_max_id": "3", "status": "ok"})
        return httpx.Response(200, json={"users": usuarios(3, 5), "next_max_id": None, "has_more": False, "status": "ok"})

    c, _ = cliente(h)
    p1 = c.pagina_seguidores("999", "teste_origem", None)
    p2 = c.pagina_seguidores("999", "teste_origem", p1.proximo)
    assert [p.usuario for p in p1.perfis] == ["teste_seguidor_0", "teste_seguidor_1", "teste_seguidor_2"]
    assert p1.proximo == "3" and p2.proximo is None and len(p2.perfis) == 2
    req = vistos[0]
    assert req.url.path == "/api/v1/friendships/999/followers/"
    assert req.headers["x-ig-app-id"] and req.headers["x-csrftoken"] == "csrf-teste"
    assert "sessionid=" in req.headers["cookie"]


def test_lista_limitada_pelo_instagram():
    c, _ = cliente(lambda r: httpx.Response(200, json={"users": usuarios(0, 2), "has_more": False,
                                                        "should_limit_list_of_followers": True, "status": "ok"}))
    p = c.pagina_seguidores("1", "teste_origem", None)
    assert p.limitada and p.proximo is None


def test_limite_429_espera_e_tenta_de_novo():
    chamadas = {"n": 0}

    def h(req):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            return httpx.Response(429, text="")
        return httpx.Response(200, json={"users": usuarios(0, 1), "status": "ok"})

    c, rel = cliente(h, esperas=(7,))
    assert len(c.pagina_seguidores("1", "teste_origem", None).perfis) == 1
    assert 7 in rel.dormiu


def test_limite_esgotado_vira_erro_limite():
    c, _ = cliente(lambda r: httpx.Response(401, json={"message": "Please wait a few minutes before you try again.", "status": "fail"}),
                   esperas=(1, 1))
    with pytest.raises(ErroLimite):
        c.pagina_seguidores("1", "teste_origem", None)


@pytest.mark.parametrize("resposta", [
    httpx.Response(400, json={"message": "checkpoint_required", "checkpoint_url": "/challenge/x", "status": "fail"}),
    httpx.Response(400, json={"message": "feedback_required", "status": "fail"}),
    httpx.Response(302, headers={"location": "https://www.instagram.com/challenge/?next=/"}),
])
def test_desafio_para_sem_contornar(resposta):
    c, _ = cliente(lambda r: resposta)
    with pytest.raises(ErroDesafio):
        c.pagina_seguidores("1", "teste_origem", None)


@pytest.mark.parametrize("resposta", [
    httpx.Response(401, json={"message": "", "status": "fail"}),
    httpx.Response(403, json={"message": "login_required", "status": "fail"}),
    httpx.Response(302, headers={"location": "https://www.instagram.com/accounts/login/"}),
])
def test_sessao_expirada(resposta):
    c, _ = cliente(lambda r: resposta)
    with pytest.raises(ErroAutenticacao):
        c.pagina_seguidores("1", "teste_origem", None)


def test_falha_de_rede_tenta_e_desiste():
    n = {"x": 0}

    def h(req):
        n["x"] += 1
        raise httpx.ConnectError("sem rede (teste)")

    c, _ = cliente(h)
    with pytest.raises(ErroIndisponivel):
        c.pagina_seguidores("1", "teste_origem", None)
    assert n["x"] == 3


def test_erro_500_tenta_de_novo_e_recupera():
    n = {"x": 0}

    def h(req):
        n["x"] += 1
        return httpx.Response(503) if n["x"] == 1 else httpx.Response(200, json={"users": [], "status": "ok"})

    c, _ = cliente(h)
    assert c.pagina_seguidores("1", "teste_origem", None).perfis == []


# Página logada fictícia: só os trechos que o coletor procura (tokens do site e id do perfil).
PAGINA_TESTE = ('<html class="_9dls"><script>["DTSGInitialData",[],{"token":"DTSG-TESTE"}]["LSD",[],{"token":"LSD-TESTE"}]'
                '["PolarisViewer",[],{"data":{"biography":"","fbid":"111"}}]"server_revision":42 '
                '"profile_id":"77" "page_id":"profilePage_77"</script></html>')
PAGINA_ERRO = '<html><script>{"polarisRouteConfig":{"pageID":"httpErrorPage"}}</script></html>'


def _graphql(req, user):
    assert req.url.path == "/graphql/query" and req.method == "POST"
    corpo = dict(x.split("=", 1) for x in req.content.decode().split("&"))
    assert corpo["fb_dtsg"] == "DTSG-TESTE" and corpo["lsd"] == "LSD-TESTE" and corpo["doc_id"]
    assert req.headers["x-fb-lsd"] == "LSD-TESTE"
    # O site responde como text/javascript, às vezes com o prefixo anti-JSON-hijacking "for (;;);".
    return httpx.Response(200, text="for (;;);" + json.dumps({"data": {"user": user}}), headers={"content-type": "text/javascript"})


def test_detalhes_graphql_e_alternativa():
    def h(req):
        if req.method == "GET" and req.url.path in ("/", "/teste_floricultura/"):
            return httpx.Response(200, text=PAGINA_TESTE)
        if req.url.path == "/graphql/query":
            return httpx.Response(200, json={"errors": [{"message": "doc_id inválido (teste)"}]})
        if req.url.path == "/api/v1/users/web_profile_info/":
            return httpx.Response(200, json={"data": {"user": {"id": "5", "username": "teste_floricultura", "full_name": "Teste Flores",
                                                               "biography": "Floricultura e coroas de flores", "category_name": "Florist",
                                                               "is_business_account": True, "is_private": False}}, "status": "ok"})
        return httpx.Response(404)

    c, _ = cliente(h)
    p = c.detalhes(Perfil(usuario="teste_floricultura", pk="5"))
    assert p.detalhes == "perfil" and p.categoria_ig == "Florist" and p.conta_comercial
    assert c._estrategias == ["web_profile_info"]  # GraphQL desativado nesta execução após erro de formato


def test_detalhes_graphql_ok():
    def h(req):
        if req.method == "GET":
            return httpx.Response(200, text=PAGINA_TESTE)
        return _graphql(req, {"pk": "5", "username": "teste_vet", "biography": "Clínica veterinária", "category": "Veterinarian",
                              "is_business": True, "account_type": 2})

    c, _ = cliente(h)
    p = c.detalhes(Perfil(usuario="teste_vet", pk="5"))
    assert p.bio == "Clínica veterinária" and p.categoria_ig == "Veterinarian" and p.conta_comercial


def test_detalhes_sem_pk_resolve_pela_pagina():
    pedidos = []

    def h(req):
        pedidos.append(req.url.path)
        if req.method == "GET":
            return httpx.Response(200, text=PAGINA_TESTE)
        return _graphql(req, {"pk": "77", "username": "teste_importado", "biography": "Funerária 24h"})

    c, _ = cliente(h)
    p = c.detalhes(Perfil(usuario="teste_importado"))
    assert p.pk == "77" and p.bio == "Funerária 24h" and pedidos[0] == "/teste_importado/"


def test_perfil_origem():
    def h(req):
        if req.method == "GET":
            assert req.headers["sec-fetch-mode"] == "navigate" and "x-requested-with" not in req.headers
            return httpx.Response(200, text=PAGINA_TESTE)
        return _graphql(req, {"pk": "77", "username": "teste_origem", "full_name": "Teste Origem", "follower_count": 4321,
                              "is_private": False, "friendship_status": {"following": True}})

    c, _ = cliente(h)
    o = c.perfil_origem("teste_origem")
    assert o == {"usuario": "teste_origem", "pk": "77", "nome": "Teste Origem", "seguidores": 4321, "privado": False,
                 "sigo": True, "verificado": False}


def test_perfil_origem_inexistente():
    c, _ = cliente(lambda r: httpx.Response(200, text=PAGINA_ERRO))
    with pytest.raises(ErroPerfil, match="não existe"):
        c.perfil_origem("teste_nao_existe")


def test_pagina_como_visitante_e_sessao_invalida():
    c, _ = cliente(lambda r: httpx.Response(200, text='<html lang="en" class="no-js not-logged-in">"profile_id":"1"</html>'))
    with pytest.raises(ErroAutenticacao):
        c.perfil_origem("teste_origem")


def test_ritmo_espaca_requisicoes():
    rel = Relogio()
    r = Ritmo(dormir=rel.dormir, agora=rel.agora, pausa_a_cada=2, pausa_longa=30)
    for _ in range(3):
        r.esperar(4)
    assert 30 in rel.dormiu
    assert all(s >= 4 for s in rel.dormiu if s != 30)


def test_ler_lista_arquivo(tmp_path):
    txt = tmp_path / "lista.txt"
    txt.write_text("instagram\n@teste_a\nteste_b;nome\n@teste_a\nhttps://instagram.com/teste_c/\ninvalido!!\n", encoding="utf-8")
    assert ler_lista_arquivo(txt) == ["teste_a", "teste_b", "teste_c"]
    meta = tmp_path / "followers_1.json"
    meta.write_text(json.dumps([{"title": "", "string_list_data": [{"href": "https://www.instagram.com/teste_d", "value": "teste_d"}]},
                                {"string_list_data": [{"value": "teste_e"}]}]), encoding="utf-8")
    assert ler_lista_arquivo(meta) == ["teste_d", "teste_e"]


def test_cookie_renovado_em_outro_dominio_nao_quebra():
    n = {"x": 0}

    def h(req):
        n["x"] += 1
        if n["x"] == 1:
            return httpx.Response(200, json={"users": usuarios(0, 1), "next_max_id": "1", "status": "ok"},
                                  headers={"set-cookie": "csrftoken=novo-teste; Domain=.instagram.com; Path=/"})
        assert req.headers["x-csrftoken"] == "novo-teste"
        return httpx.Response(200, json={"users": usuarios(1, 2), "status": "ok"})

    c, _ = cliente(h)
    c.pagina_seguidores("1", "teste_origem", None)
    assert len(c.pagina_seguidores("1", "teste_origem", "1").perfis) == 1
