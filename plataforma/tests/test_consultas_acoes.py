"""Estados das execuções, filtros (no SQL), detalhes e as ações que disparam as automações (processos simulados)."""

import json
from datetime import datetime, timedelta

import pytest

from plataforma import acoes, consultas, db, sincronizar
from tests.conftest import Ambiente, perfil

R = Ambiente.registro


@pytest.fixture
def base_teste(amb):
    loc = lambda c, u: {"cidade": [(c, "cadastro", True)], "uf": [(u, "cadastro", True)]}
    amb.lote("2026-10-18_100000_curitiba", [
        R(1, "Funerária Teste | Curitiba/PR", loc("Curitiba", "PR") | {"cnpj": [("11.222.333/0001-81", "site", True)],
          "categoria": [("Funerária / serviços funerários", "cadastro", True)], "telefones": [("(41) 3333-3333", "site", True)]},
          data="2026-10-18T10:00:00"),
        R(2, "Floricultura Teste | Curitiba/PR", loc("Curitiba", "PR") | {"categoria": [("Floricultura", "gerado", False)],
          "whatsapp": [("(41) 99999-9999", "site", True)]}, data="2026-10-18T10:00:00"),
        R(3, "Padaria Teste | São Paulo/SP", loc("São Paulo", "SP") | {"categoria": [("Padaria / confeitaria", "cadastro", True)],
          "cnpj": [("44.555.666/0001-02", "busca", False)]}, data="2026-06-01T10:00:00"),
    ])
    amb.lote("2026-10-19_100000_sp", [
        R(1, "Cemitério Teste | Sao Paulo/SP", loc("Sao Paulo", "SP") | {"categoria": [("Cemitério", "cadastro", True)],
          "instagram": [("https://www.instagram.com/teste_cemiterio/", "site", True)]}, data="2026-10-19T10:00:00"),
    ])
    amb.analise("origem_teste", [
        perfil("teste_cemiterio", "Cemitério Teste", "Cemitério parque e jazigos"),
        perfil("teste_pet", "Teste Pet", "Crematório pet e cemitério de animais", cidade="Londrina, Paraná"),
        perfil("teste_flores", "Flores Teste", "Floricultura: coroas de flores para velórios"),
        perfil("maria_teste", "Maria Teste", "Mãe, esposa e cristã"),
    ])
    sincronizar.sincronizar()
    return amb


def _nomes(f):
    return sorted(e["nome"] for e in consultas.listar_empresas(f)["itens"])


# ------------------------------------------------------------------ estados das execuções

def _exec(eid):
    return db.conexao().execute("SELECT * FROM execucoes WHERE id=?", (eid,)).fetchone()


def test_estados_do_instagram(amb):
    agora = datetime.now()
    casos = {
        "concluida": {"status": "concluido"},
        "concluida_parcial": {"status": "limite_atingido", "fim_lista": False},
        "em_andamento": {"status": "executando", "fim_lista": False, "atualizado": agora.isoformat(timespec="seconds")},
        "parada": {"status": "executando", "fim_lista": False, "atualizado": (agora - timedelta(hours=1)).isoformat(timespec="seconds")},
        "pausada": {"status": "pausado_limite_instagram", "fim_lista": False},
        "precisa_acao": {"status": "erro_desafio", "fim_lista": False},
    }
    for i, (esperado, est) in enumerate(casos.items()):
        amb.analise(f"origem{i}", [perfil(f"teste_{i}", "Funerária Teste", "funerária")], est, nome=f"2026-10-20_10000{i}_{esperado}")
    sincronizar.sincronizar()
    for i, esperado in enumerate(casos):
        x = _exec(f"ig:2026-10-20_10000{i}_{esperado}")
        assert x["estado"] == esperado, (esperado, x["estado"])
    assert _exec("ig:2026-10-20_100000_concluida")["completa"] == 1
    assert _exec("ig:2026-10-20_100001_concluida_parcial")["completa"] == 0  # limite não é varredura completa
    assert _exec("ig:2026-10-20_100001_concluida_parcial")["pode_retomar"] == 1
    assert _exec("ig:2026-10-20_100003_parada")["pode_retomar"] == 1


def test_lista_limitada_pelo_instagram_nao_conta_como_completa(amb):
    amb.analise("origem", [perfil("teste_1", "x", "funerária")], {"status": "concluido", "lista_limitada": True})
    sincronizar.sincronizar()
    x = db.conexao().execute("SELECT * FROM execucoes").fetchone()
    assert x["estado"] == "concluida_parcial" and x["completa"] == 0


def test_estados_da_pesquisa_de_empresas(amb):
    velho = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
    amb.lote("2026-10-20_100000_ok", [R(1, "Padaria Teste | Bauru/SP")])
    amb.lote("2026-10-20_100001_erro", [R(1, "Padaria Teste | Bauru/SP"), R(2, "Mercado Teste | Bauru/SP", status="erro")])
    amb.lote("2026-10-20_100002_morto", [R(1, "Padaria Teste | Bauru/SP")], status="executando", progresso_extra={"atualizado": velho})
    amb.lote("2026-10-20_100003_vivo", [R(1, "Padaria Teste | Bauru/SP")], status="executando",
             progresso_extra={"atualizado": datetime.now().isoformat(timespec="seconds")})
    sincronizar.sincronizar()
    assert _exec("emp:2026-10-20_100000_ok")["estado"] == "concluida"
    e = _exec("emp:2026-10-20_100001_erro")
    assert e["estado"] == "concluida_com_falhas" and e["falhas"] == 1 and e["pode_retomar"] == 1 and e["completa"] == 0
    assert _exec("emp:2026-10-20_100002_morto")["estado"] == "parada"
    assert _exec("emp:2026-10-20_100003_vivo")["estado"] == "em_andamento"


def test_pasta_apagada_sai_da_base_e_arquivar_esconde(amb):
    p = amb.lote("2026-10-20_100000_a", [R(1, "Padaria Teste | Bauru/SP")])
    amb.lote("2026-10-20_100001_b", [R(1, "Mercado Teste | Bauru/SP")])
    sincronizar.sincronizar()
    sincronizar.arquivar("emp:2026-10-20_100001_b", True)
    assert _nomes({}) == ["Padaria Teste"]
    assert len(consultas.listar_empresas({"ocultas": "1"})["itens"]) == 2
    import shutil
    shutil.rmtree(p)
    assert sincronizar.sincronizar()["removidas"] == 1
    assert _nomes({}) == []
    sincronizar.arquivar("emp:2026-10-20_100001_b", False)
    assert _nomes({}) == ["Mercado Teste"]


# ------------------------------------------------------------------ filtros

def test_filtros_individuais(base_teste):
    assert _nomes({"uf": "PR"}) == ["Floricultura Teste", "Funerária Teste"]
    assert _nomes({"cidade": "São Paulo"}) == ["Cemitério Teste", "Padaria Teste"]  # com e sem acento
    assert _nomes({"status": "identificada"}) == ["Funerária Teste"]
    assert _nomes({"q": "floricultura curitiba"}) == ["Floricultura Teste"]
    assert _nomes({"q": "11222333"}) == ["Funerária Teste"]          # CNPJ só com dígitos
    assert _nomes({"q": "teste_cemiterio"}) == ["Cemitério Teste"]   # @ do Instagram
    assert _nomes({"contato": "sem"}) == ["Cemitério Teste", "Padaria Teste"]
    assert _nomes({"contato": "whatsapp"}) == ["Floricultura Teste"]
    assert _nomes({"instagram": "vinculado"}) == ["Cemitério Teste"]
    assert _nomes({"pendencia": "nao_confirmados"}) == ["Floricultura Teste", "Padaria Teste"]
    assert _nomes({"pendencia": "desatualizada"}) == ["Padaria Teste"]
    assert _nomes({"execucao": "emp:2026-10-19_100000_sp"}) == ["Cemitério Teste"]
    assert _nomes({"desde": "2026-10-19"}) == ["Cemitério Teste"]
    assert _nomes({"ate": "2026-10-01"}) == ["Padaria Teste"]


def test_filtro_de_segmento_por_origem(base_teste):
    assert _nomes({"segmento": "C"}) == ["Cemitério Teste"]
    assert _nomes({"segmento": "C", "origem_segmento": "perfil"}) == ["Cemitério Teste"]  # perfil vinculado e identificado
    assert _nomes({"segmento": "F", "origem_segmento": "inferido"}) == ["Funerária Teste"]
    assert _nomes({"segmento": "F", "origem_segmento": "perfil"}) == []
    assert _nomes({"segmento": "D,F"}) == ["Floricultura Teste", "Funerária Teste"]
    assert _nomes({"origem_segmento": "sem"}) == ["Padaria Teste"]


def test_filtros_combinados_ordenacao_paginacao_e_vazio(base_teste):
    assert _nomes({"uf": "PR", "segmento": "F", "contato": "com"}) == ["Funerária Teste"]
    assert _nomes({"uf": "SP", "status": "identificada"}) == []
    d = consultas.listar_empresas({"ordenar": "-ultima_pesquisa", "por_pagina": "2", "pagina": "2"})
    assert d["total"] == 4 and d["paginas"] == 2 and len(d["itens"]) == 2
    assert [e["nome"] for e in consultas.listar_empresas({"ordenar": "-ultima_pesquisa"})["itens"]][0] == "Cemitério Teste"
    assert consultas.listar_empresas({"ordenar": "DROP TABLE empresas"})["total"] == 4  # ordem fora da lista é ignorada
    assert consultas.listar_empresas({"q": "x' OR 1=1 --"})["total"] == 0


def test_opcoes_e_detalhe(base_teste):
    op = consultas.opcoes_empresas()
    cidades = {(c["valor"], c["uf"]): c["n"] for c in op["cidades"]}
    assert cidades[("São Paulo", "SP")] == 2  # "Sao Paulo" e "São Paulo" viram uma opção
    eid = consultas.listar_empresas({"q": "floricultura"})["itens"][0]["id"]
    d = consultas.detalhe_empresa(eid)
    estados = {c["campo"]: c["estado"] for c in d["campos"]}
    assert estados["categoria"] == "nao_confirmado" and estados["whatsapp"] == "confirmado" and estados["cnpj"] == "nao_encontrado"
    assert d["historico"][0]["atual"] and d["atual"]["execucao_id"] == "emp:2026-10-18_100000_curitiba"


def test_perfis_filtros_e_pendencias(base_teste):
    sit = lambda f: sorted(p["usuario"] for p in consultas.listar_perfis(f)["itens"])
    assert sit({"situacao": "identificado", "empresa": "sem"}) == ["teste_flores", "teste_pet"]
    assert sit({"empresa": "com"}) == ["teste_cemiterio"]
    assert sit({"segmento": "D"}) == ["teste_flores"]
    vg = consultas.visao_geral()
    assert vg["perfis"]["sem_pesquisa"] == 2 and vg["empresas"]["total"] == 4


# ------------------------------------------------------------------ ações

def test_pesquisar_empresas_da_analise_pula_as_ja_pesquisadas(base_teste):
    eid = "ig:" + db.conexao().execute("SELECT nome FROM execucoes WHERE tipo='instagram'").fetchone()[0]
    c = acoes.candidatos_da_execucao(eid)
    linhas = {s["usuario"]: s["linha"] for s in c["selecionados"]}
    assert set(linhas) == {"teste_pet", "teste_flores"}
    assert linhas["teste_pet"] == "Teste Pet | @teste_pet | Londrina/PR"
    assert [p["usuario"] for p in c["pulados"]] == ["teste_cemiterio"]  # empresa pesquisada há menos de 30 dias
    assert {s["usuario"] for s in acoes.candidatos_da_execucao(eid, incluir_pesquisadas=True)["selecionados"]} >= {"teste_cemiterio"}
    assert [s["usuario"] for s in acoes.candidatos_da_execucao(eid, segmentos=["D"])["selecionados"]] == ["teste_flores"]
    novo = acoes.pesquisar_empresas_da_execucao(eid, segmentos=["D"])
    assert novo.startswith("emp:")
    _, pasta = sincronizar.pasta_da_execucao(novo)
    meta = json.loads((pasta / "plataforma.json").read_text(encoding="utf-8"))
    assert meta["origem_execucao"] == eid
    assert (pasta / "entrada.txt").read_text(encoding="utf-8").strip() == "Flores Teste | @teste_flores"
    assert base_teste.processos[-1][-2:] == ["retomar", str(pasta)]
    assert db.conexao().execute("SELECT origem_execucao FROM execucoes WHERE id=?", (novo,)).fetchone()[0] == eid


def test_validacao_da_nova_pesquisa(amb):
    with pytest.raises(acoes.AcaoInvalida):
        acoes.iniciar_empresas("   \n  ")
    with pytest.raises(acoes.AcaoInvalida):
        acoes.iniciar_empresas("\n".join(f"Empresa {i}" for i in range(1001)))
    with pytest.raises(acoes.AcaoInvalida):
        acoes.iniciar_empresas("# só comentário")
    assert amb.processos == []
    eid = acoes.iniciar_empresas("Padaria Teste | Bauru/SP\n@teste_loja", "minha lista")
    assert "minha-lista" in eid and len(amb.processos) == 1


def test_atualizar_repete_a_entrada_e_mantem_historico(base_teste):
    eid = consultas.listar_empresas({"q": "padaria"})["itens"][0]["id"]
    novo = acoes.atualizar_empresas([eid])
    _, pasta = sincronizar.pasta_da_execucao(novo)
    assert (pasta / "entrada.txt").read_text(encoding="utf-8").strip() == "Padaria Teste | São Paulo/SP"


def test_retomar_e_parar_respeitam_o_estado(amb):
    p = amb.lote("2026-10-20_100000_a", [R(1, "Padaria Teste | Bauru/SP")], status="interrompido")
    sincronizar.sincronizar()
    with pytest.raises(acoes.AcaoInvalida):
        acoes.parar("emp:2026-10-20_100000_a")
    acoes.retomar("emp:2026-10-20_100000_a")
    assert amb.processos[-1][-2:] == ["retomar", str(p)]
    vivo = amb.lote("2026-10-20_100001_b", [R(1, "Padaria Teste | Bauru/SP")], status="executando",
                    progresso_extra={"atualizado": datetime.now().isoformat(timespec="seconds")})
    with pytest.raises(acoes.AcaoInvalida):
        acoes.retomar("emp:2026-10-20_100001_b")
    acoes.parar("emp:2026-10-20_100001_b")
    assert (vivo / "parar").exists()
    with pytest.raises(acoes.AcaoInvalida):
        acoes.retomar("emp:../../etc")


def test_iniciar_analise_do_instagram_valida_e_dispara(amb):
    with pytest.raises(acoes.AcaoInvalida):
        acoes.iniciar_instagram({"origem": "@@ inválido"})
    with pytest.raises(acoes.AcaoInvalida):
        acoes.iniciar_instagram({"origem": "@teste_origem", "limite": "-5"})
    eid = acoes.iniciar_instagram({"origem": "@Teste_Origem", "limite": "50", "categorias": ["F", "G"], "noite": True})
    _, pasta = sincronizar.pasta_da_execucao(eid)
    cfg = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    assert cfg["origem"] == "teste_origem" and cfg["limite"] == 50 and cfg["categorias"] == ["F", "G"] and cfg["noite"]
    assert amb.processos[-1][-3:] == ["prospeccao", "executar", str(pasta)]
