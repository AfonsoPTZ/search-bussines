"""Fila de pesquisa: a ligação entre a análise do Instagram e a pesquisa de empresas.

Dados fictícios, sem internet. A fila é derivada, mas o que você decide (dispensar) não é desfeito sozinho.
"""

import pytest

from plataforma import acoes, db, fila, sincronizar
from tests.conftest import perfil

R = None  # preenchido por amb.registro nos testes que precisam


def _fila(estado="pendente"):
    return {i["usuario"] for i in fila.listar(estado)}


def test_perfil_identificado_entra_na_fila_e_quem_nao_e_nao_entra(amb):
    amb.analise("origem_teste", [
        perfil("teste_funeraria", "Funerária Teste", "Funerária e plano funeral 24h", cidade="Curitiba"),
        perfil("teste_floricultura", "Flores Teste", "Floricultura e coroas de flores", cidade="Bauru"),
        perfil("teste_pessoa", "Joana", "Mãe do Pedro, amo flores"),  # pessoal: não identificado
    ])
    sincronizar.sincronizar()
    pendentes = _fila()
    assert "teste_funeraria" in pendentes
    assert "teste_floricultura" in pendentes
    assert "teste_pessoa" not in pendentes

    r = fila.resumo()
    assert r["pendentes"] == len(pendentes)
    assert r["por_segmento"].get("F") == 1 and r["por_segmento"].get("D") == 1


def test_linha_da_fila_tem_nome_arroba_e_cidade(amb):
    amb.analise("origem_teste", [perfil("teste_funeraria", "Funerária Teste", "Funerária 24h", cidade="Curitiba")])
    sincronizar.sincronizar()
    item = fila.listar("pendente")[0]
    assert item["linha"].startswith("Funerária Teste | @teste_funeraria")
    assert "Curitiba" in item["linha"]
    assert item["segmentos"] == ["F"]
    assert item["analise"] == "@origem_teste"


def test_sincronizar_e_idempotente(amb):
    amb.analise("origem_teste", [perfil("teste_funeraria", "Funerária Teste", "Funerária 24h")])
    sincronizar.sincronizar()
    antes = fila.listar("pendente")
    sincronizar.sincronizar()
    sincronizar.sincronizar()
    depois = fila.listar("pendente")
    assert [i["usuario"] for i in antes] == [i["usuario"] for i in depois]
    assert [i["criado"] for i in antes] == [i["criado"] for i in depois]  # não recria nem "renova" quem já esperava


def test_sai_da_fila_quando_a_empresa_e_encontrada(amb):
    amb.analise("origem_teste", [perfil("teste_funeraria", "Funerária Teste", "Funerária 24h")])
    sincronizar.sincronizar()
    assert "teste_funeraria" in _fila("pendente")

    # a pesquisa de empresas partiu do @: o vínculo nasce confirmado
    amb.lote("2026-10-20_110000_fila", [amb.registro(1, "Funerária Teste | @teste_funeraria | Curitiba/PR")])
    sincronizar.sincronizar()

    assert "teste_funeraria" not in _fila("pendente")
    concluidos = fila.listar("concluido")
    assert [i["usuario"] for i in concluidos] == ["teste_funeraria"]
    assert concluidos[0]["empresa_id"] is not None


def test_dispensar_tira_da_fila_e_nao_volta_sozinho(amb):
    amb.analise("origem_teste", [perfil("teste_funeraria", "Funerária Teste", "Funerária 24h")])
    sincronizar.sincronizar()

    assert fila.dispensar("teste_funeraria", "perfil pessoal") == 1
    assert "teste_funeraria" not in _fila("pendente")
    assert "teste_funeraria" in _fila("dispensado")

    sincronizar.sincronizar()  # várias sincronizações não desfazem a sua decisão
    sincronizar.sincronizar()
    assert "teste_funeraria" not in _fila("pendente")
    assert fila.listar("dispensado")[0]["motivo"] == "perfil pessoal"

    assert fila.reabrir("teste_funeraria") == 1
    assert "teste_funeraria" in _fila("pendente")


def test_pesquisar_fila_cria_lote_e_marca_como_pesquisando(amb):
    amb.analise("origem_teste", [
        perfil("teste_funeraria", "Funerária Teste", "Funerária 24h", cidade="Curitiba"),
        perfil("teste_floricultura", "Flores Teste", "Floricultura e coroas", cidade="Bauru"),
    ])
    sincronizar.sincronizar()

    eid = acoes.pesquisar_fila()
    assert eid.startswith("emp:")
    assert amb.processos, "deveria ter iniciado o processo da pesquisa de empresas"

    assert _fila("pendente") == set()
    assert _fila("pesquisando") == {"teste_funeraria", "teste_floricultura"}

    # a lista enviada é a das linhas da fila
    entrada = (sincronizar.pasta_da_execucao(eid)[1] / "entrada.txt").read_text(encoding="utf-8")
    assert "@teste_funeraria" in entrada and "@teste_floricultura" in entrada
    assert "Curitiba" in entrada


def test_pesquisar_fila_respeita_limite_e_segmento(amb):
    amb.analise("origem_teste", [
        perfil("teste_funeraria", "Funerária Teste", "Funerária 24h"),
        perfil("teste_floricultura", "Flores Teste", "Floricultura e coroas de flores"),
    ])
    sincronizar.sincronizar()

    acoes.pesquisar_fila(segmentos=["D"])
    assert _fila("pesquisando") == {"teste_floricultura"}
    assert _fila("pendente") == {"teste_funeraria"}


def test_pesquisar_fila_vazia_avisa_em_vez_de_criar_lote(amb):
    with pytest.raises(acoes.AcaoInvalida):
        acoes.pesquisar_fila()
    assert not amb.processos


def test_fila_ignora_analise_arquivada(amb):
    pasta = amb.analise("origem_teste", [perfil("teste_funeraria", "Funerária Teste", "Funerária 24h")])
    sincronizar.sincronizar()
    assert "teste_funeraria" in _fila("pendente")

    sincronizar.arquivar("ig:" + pasta.name, True)
    assert "teste_funeraria" not in _fila("pendente")

    sincronizar.arquivar("ig:" + pasta.name, False)
    assert "teste_funeraria" in _fila("pendente")


def test_estado_invalido_e_recusado(amb):
    with pytest.raises(ValueError):
        fila.listar("inventado")
    with pytest.raises(ValueError):
        fila.marcar(["x"], "inventado")


def test_api_da_fila(amb):
    from plataforma import servidor
    amb.analise("origem_teste", [perfil("teste_funeraria", "Funerária Teste", "Funerária 24h")])
    sincronizar.sincronizar()

    d = servidor.rota_get("/api/fila", {})
    assert d["resumo"]["pendentes"] == 1
    assert d["itens"][0]["usuario"] == "teste_funeraria"
    assert any(s["codigo"] == "F" for s in d["segmentos"])

    # o contador que aparece no menu lateral
    status = servidor.rota_get("/api/status", {})
    assert status["pendencias"]["fila_pendentes"] == 1

    servidor.rota_post("/api/fila/dispensar", {"usuarios": ["teste_funeraria"], "motivo": "teste"})
    assert servidor.rota_get("/api/fila", {})["resumo"]["pendentes"] == 0
