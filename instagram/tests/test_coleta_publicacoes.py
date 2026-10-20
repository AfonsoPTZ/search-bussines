"""Coleta de publicações e destaques contra um Instagram SIMULADO. Estrutura baseada na resposta real observada em
19/10/2026 (inclusive o erro parcial em location.profile_pic_url). DADOS DE TESTE FICTÍCIOS."""

import httpx
import pytest

from prospeccao.coleta import ErroColeta, ErroLimite
from tests.test_coleta import PAGINA_TESTE, cliente


def _no(texto, fixado=False, local=None, codigo="x"):
    return {"node": {"caption": {"text": texto} if texto is not None else None, "timeline_pinned_user_ids": ["1"] if fixado else [],
                     "location": {"name": local, "profile_pic_url": None} if local else None, "taken_at": 1, "code": codigo}}


def test_publicacoes_fixados_hashtags_local_e_erro_parcial():
    def h(req):
        if req.method == "GET":
            return httpx.Response(200, text=PAGINA_TESTE)
        corpo = req.content.decode()
        assert "PolarisProfilePostsQuery" in corpo and "teste_placas" in corpo
        return httpx.Response(200, json={
            "data": {"xdt_api__v1__feed__user_timeline_graphql_connection": {"edges": [
                _no("Placas em bronze #placaspersonalizadas #marmoraria", fixado=True, local="Marmoraria Teste", codigo="a"),
                _no(None, codigo="b"),
                _no("Promoção de verão", codigo="c")]}},
            # erro parcial real: a foto do local falha, mas os posts vêm
            "errors": [{"message": "A server error field_exception occured.", "path": ["xdt", "edges", 0, "node", "location", "profile_pic_url"]}]})

    c, _ = cliente(h)
    posts = c.publicacoes("teste_placas")
    assert len(posts) == 3 and posts[0]["fixado"] and not posts[2]["fixado"]
    assert posts[0]["hashtags"] == ["marmoraria", "placaspersonalizadas"] and posts[0]["local"] == "Marmoraria Teste"
    assert posts[1]["texto"] == "" and posts[1]["hashtags"] == []


def test_publicacoes_sem_dados_e_erro():
    def h(req):
        if req.method == "GET":
            return httpx.Response(200, text=PAGINA_TESTE)
        return httpx.Response(200, json={"data": None, "errors": [{"message": "execution error (teste)"}]})

    c, _ = cliente(h)
    with pytest.raises(ErroColeta):
        c.publicacoes("teste_x")


def test_perfil_sem_publicacoes():
    def h(req):
        if req.method == "GET":
            return httpx.Response(200, text=PAGINA_TESTE)
        return httpx.Response(200, json={"data": {"xdt_api__v1__feed__user_timeline_graphql_connection": {"edges": []}}})

    c, _ = cliente(h)
    assert c.publicacoes("teste_x") == []


def test_destaques():
    def h(req):
        assert req.url.params.get("query_hash") and req.method == "GET"
        return httpx.Response(200, json={"data": {"user": {"edge_highlight_reels": {"edges": [
            {"node": {"title": "Planos"}}, {"node": {"title": " Coroas "}}, {"node": {"title": ""}}]}}}, "status": "ok"})

    c, _ = cliente(h)
    assert c.destaques("77") == ["Planos", "Coroas"]


def test_limite_em_publicacoes_propaga_para_pausar():
    def h(req):
        if req.method == "GET":
            return httpx.Response(200, text=PAGINA_TESTE)
        return httpx.Response(429)

    c, _ = cliente(h, esperas=())
    with pytest.raises(ErroLimite):
        c.publicacoes("teste_x")
