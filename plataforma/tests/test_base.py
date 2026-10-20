"""Reconhecimento da mesma empresa, duplicidades, vínculos com perfis, segmentos e decisões manuais."""

import json

import pytest

from plataforma import base, db, normalizar, sincronizar
from tests.conftest import Ambiente, perfil

R = Ambiente.registro
CNPJ_A = "11.222.333/0001-81"
CNPJ_B = "44.555.666/0001-02"


def _empresas():
    return [dict(r) for r in db.conexao().execute("SELECT * FROM empresas ORDER BY id")]


def _cnpj(valor, confirmado=True):
    return {"cnpj": [(valor, "site", confirmado)]}


# ------------------------------------------------------------------ normalização

def test_chave_de_dominio_nao_une_hospedagem_compartilhada():
    assert normalizar.chave_dominio("https://www.loja.com.br/contato") == "loja.com.br"
    assert normalizar.chave_dominio("https://fulano.wixsite.com/padaria") == "fulano.wixsite.com/padaria"
    assert normalizar.chave_dominio("https://outro.wixsite.com/padaria") != normalizar.chave_dominio("https://fulano.wixsite.com/padaria")
    assert normalizar.chave_dominio("https://padaria.negocio.site/") == "padaria.negocio.site"
    assert normalizar.chave_dominio("https://linktr.ee/x") == ""
    assert normalizar.chave_dominio("https://wa.me/5511999999999") == ""


def test_normalizacoes_para_a_lista_de_empresas():
    assert normalizar.handle_de_url("https://www.instagram.com/Teste_Funeraria/") == "teste_funeraria"
    assert normalizar.handle_de_url("https://www.instagram.com/p/abc/") == ""
    assert normalizar.cidade_para_pesquisa("Alpestre, Rio Grande do Sul") == "Alpestre/RS"
    assert normalizar.cidade_para_pesquisa("Curitiba") == "Curitiba"
    assert normalizar.nome_para_pesquisa("Funerária X (93) 99212-7740 | 24h; 🕊️") == "Funerária X 24h"


# ------------------------------------------------------------------ mesma empresa

def test_mesmo_cnpj_confirmado_em_lotes_diferentes_vira_uma_empresa(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "Funerária Teste | Curitiba/PR", _cnpj(CNPJ_A), data="2026-10-18T10:00:00")])
    amb.lote("2026-10-19_100000_b", [R(1, "www.funerariateste.com.br", _cnpj(CNPJ_A), data="2026-10-19T10:00:00")])
    sincronizar.sincronizar()
    assert len(_empresas()) == 1
    assert _empresas()[0]["n_pesquisas"] == 2


def test_mesmo_arroba_informado_vira_uma_empresa(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "@teste_floricultura")])
    amb.lote("2026-10-19_100000_b", [R(1, "Floricultura Teste | @teste_floricultura | Londrina/PR")])
    sincronizar.sincronizar()
    assert len(_empresas()) == 1


def test_mesma_entrada_repetida_vira_uma_empresa_mesmo_sem_identificador(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "Padaria Teste | Bauru/SP")])
    amb.lote("2026-10-19_100000_b", [R(1, "Padaria Teste | Bauru/SP")])
    sincronizar.sincronizar()
    assert len(_empresas()) == 1


def test_nome_igual_nunca_une_so_sugere_duplicidade_na_mesma_uf(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "Padaria Teste | Bauru/SP", {"cidade": [("Bauru", "site", True)], "uf": [("SP", "site", True)]}),
                                     R(2, "Padaria Teste Ltda | Marília/SP", {"cidade": [("Marília", "site", True)], "uf": [("SP", "site", True)]}),
                                     R(3, "Padaria Teste | Recife/PE", {"cidade": [("Recife", "site", True)], "uf": [("PE", "site", True)]})])
    sincronizar.sincronizar()
    assert len(_empresas()) == 3
    dups = db.conexao().execute("SELECT * FROM duplicidades").fetchall()
    assert len(dups) == 1 and dups[0]["estado"] == "pendente" and "mesmo nome" in dups[0]["motivo"]


def test_cnpjs_confirmados_diferentes_nao_unem_mesmo_com_o_mesmo_arroba(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "@teste_rede", _cnpj(CNPJ_A))])
    amb.lote("2026-10-19_100000_b", [R(1, "Rede Teste | @teste_rede", _cnpj(CNPJ_B))])
    sincronizar.sincronizar()
    assert len(_empresas()) == 2
    d = db.conexao().execute("SELECT motivo FROM duplicidades").fetchone()
    assert "CNPJs confirmados são diferentes" in d["motivo"]


def test_matriz_e_filial_mesma_raiz_nao_sao_conflito(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "@teste_rede", _cnpj("11.222.333/0001-81"))])
    amb.lote("2026-10-19_100000_b", [R(1, "@teste_rede", _cnpj("11.222.333/0002-62"))])
    sincronizar.sincronizar()
    assert len(_empresas()) == 1


def test_cnpj_nao_confirmado_nao_une_empresas(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "Padaria Um | Bauru/SP", _cnpj(CNPJ_A, False)),
                                     R(2, "Mercado Dois | Ourinhos/SP", _cnpj(CNPJ_A, False))])
    sincronizar.sincronizar()
    assert len(_empresas()) == 2


def test_exibe_a_pesquisa_mais_recente_sem_erro_e_guarda_o_historico(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "@teste_loja", {"telefones": [("(11) 1111-1111", "site", True)]}, data="2026-10-18T10:00:00")])
    amb.lote("2026-10-19_100000_b", [R(1, "@teste_loja", {"telefones": [("(11) 2222-2222", "site", True)]}, data="2026-10-19T10:00:00")])
    amb.lote("2026-10-20_100000_c", [R(1, "@teste_loja", data="2026-10-20T10:00:00", status="erro")])
    sincronizar.sincronizar()
    e = _empresas()[0]
    assert e["telefone"] == "(11) 2222-2222" and e["n_pesquisas"] == 3
    assert e["pesquisa_atual"] == "emp:2026-10-19_100000_b#1"


def test_sincronizacao_e_idempotente(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "@teste_loja"), R(2, "Padaria Teste | Bauru/SP")])
    assert sincronizar.sincronizar() == {"dados": 1}
    antes = _empresas()
    assert sincronizar.sincronizar() == {}
    assert [e["id"] for e in _empresas()] == [e["id"] for e in antes]


# ------------------------------------------------------------------ decisões manuais

def test_unir_e_separar_persistem_apos_reimportar(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "Padaria Teste | Bauru/SP"), R(2, "Padaria Teste Centro | Bauru/SP")])
    sincronizar.sincronizar()
    a, b = [e["id"] for e in _empresas()]
    with db.transacao() as c:
        base.unir(c, a, b)
    assert len(_empresas()) == 1
    sincronizar.sincronizar(forcar=True)
    assert len(_empresas()) == 1 and _empresas()[0]["n_pesquisas"] == 2
    with db.transacao() as c:
        nova = base.separar(c, "emp:2026-10-18_100000_a#2")
    sincronizar.sincronizar(forcar=True)
    assert len(_empresas()) == 2
    d = db.conexao().execute("SELECT estado FROM duplicidades WHERE a=? AND b=?", tuple(sorted((a, nova)))).fetchone()
    assert d["estado"] == "diferentes"


def test_decisao_diferentes_nao_volta_como_sugestao(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "Padaria Teste | Bauru/SP"), R(2, "Padaria Teste Ltda | Bauru/SP")])
    sincronizar.sincronizar()
    d = db.conexao().execute("SELECT a, b FROM duplicidades").fetchone()
    with db.transacao() as c:
        base.decidir_duplicidade(c, d["a"], d["b"], "diferentes")
    sincronizar.sincronizar(forcar=True)
    assert db.conexao().execute("SELECT estado FROM duplicidades").fetchone()["estado"] == "diferentes"
    assert len(_empresas()) == 2


def test_decisao_invalida_e_recusada(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "Padaria Teste | Bauru/SP"), R(2, "Padaria Teste Ltda | Bauru/SP")])
    sincronizar.sincronizar()
    d = db.conexao().execute("SELECT a, b FROM duplicidades").fetchone()
    with pytest.raises(ValueError), db.transacao() as c:
        base.decidir_duplicidade(c, d["a"], d["b"], "talvez")


# ------------------------------------------------------------------ vínculos e segmentos

def test_vinculos_confirmado_pela_entrada_e_sugerido_pela_busca(amb):
    amb.lote("2026-10-18_100000_a", [
        R(1, "@teste_funeraria"),
        R(2, "Cemitério Teste | Curitiba/PR", {"instagram": [("https://www.instagram.com/teste_cemiterio/", "busca", False)]}),
        R(3, "Floricultura Teste | Curitiba/PR", {"instagram": [("https://www.instagram.com/teste_flores/", "site", True)]}),
    ])
    sincronizar.sincronizar()
    v = {r["usuario"]: dict(r) for r in db.conexao().execute("SELECT * FROM vinculos")}
    assert v["teste_funeraria"]["estado"] == "confirmado" and v["teste_funeraria"]["origem"] == "entrada"
    assert v["teste_cemiterio"]["estado"] == "sugerido"
    assert v["teste_flores"]["estado"] == "confirmado" and v["teste_flores"]["origem"] == "site"


def test_rejeicao_manual_sobrevive_a_nova_sincronizacao(amb):
    pasta = amb.lote("2026-10-18_100000_a", [R(1, "@teste_funeraria")])
    sincronizar.sincronizar()
    eid = _empresas()[0]["id"]
    with db.transacao() as c:
        base.decidir_vinculo(c, "teste_funeraria", eid, "rejeitado", "outra empresa")
    (pasta / "registros.jsonl").write_text(json.dumps(R(1, "@teste_funeraria", data="2026-10-20T11:00:00")) + "\n", encoding="utf-8")
    sincronizar.sincronizar()
    assert db.conexao().execute("SELECT estado FROM vinculos").fetchone()["estado"] == "rejeitado"


def test_segmento_vem_do_perfil_vinculado_e_inferido_fica_separado(amb):
    """O segmento da empresa vem, nesta ordem: do perfil vinculado e identificado; do segmento que a pesquisa
    resolveu pelo CNAE/site; e só então da inferência pelo nome. Empresa fora dos 13 segmentos fica sem nenhum."""
    amb.analise("origem_teste", [perfil("teste_funeraria", "Funerária Teste", "Funerária e plano funeral 24h")])
    amb.lote("2026-10-18_100000_a", [
        R(1, "@teste_funeraria", {"categoria": [("F · Crematórios e funerárias humanas", "cadastro", True)]}),
        # O CNAE diz F: é isso que vale, e o "Catedral" do nome não transforma a funerária em igreja.
        R(2, "Funerária Catedral | Curitiba/PR", {"razao_social": [("FUNERARIA CATEDRAL LTDA", "cadastro", True)],
                                                  "categoria": [("F · Crematórios e funerárias humanas", "cadastro", True)]}),
        # Padaria não é nenhum dos 13 segmentos: a pesquisa não dá segmento nenhum a ela.
        R(3, "Padaria Teste | Bauru/SP", {})])
    sincronizar.sincronizar()
    por_nome = {e["nome"]: e for e in _empresas()}
    assert "F" in por_nome["@teste_funeraria"]["segmentos_perfil"]
    catedral = por_nome["Funerária Catedral"]
    assert catedral["segmentos_perfil"] == "" and catedral["segmentos_inferidos"] == ",F,"
    assert "J" not in catedral["segmentos_inferidos"]  # razão social é nome, não tipo de negócio
    assert por_nome["Padaria Teste"]["segmentos_inferidos"] == ""


def test_link_da_bio_para_o_site_confirmado_gera_vinculo_sugerido(amb):
    amb.lote("2026-10-18_100000_a", [R(1, "Cemitério Teste | Curitiba/PR", {"site": [("https://www.cemiterioteste.com.br/", "site", True)]})])
    amb.analise("origem_teste", [perfil("teste_cemiterio", "Cemitério Teste", "Cemitério parque", link="https://cemiterioteste.com.br/planos")])
    sincronizar.sincronizar()
    v = db.conexao().execute("SELECT * FROM vinculos WHERE usuario='teste_cemiterio'").fetchone()
    assert v["estado"] == "sugerido" and v["origem"] == "dominio"
