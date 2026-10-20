"""Triagem em etapas (só @ e nome). DADOS DE TESTE FICTÍCIOS."""

import json

import pytest

from prospeccao import triagem
from prospeccao.perfis import Perfil


@pytest.mark.parametrize("usuario,nome,esperado", [
    ("teste_funerariax", "", triagem.SEGMENTO),
    ("pax.testeregional", "PAX TESTE", triagem.SEGMENTO),       # "pax": marca de funerárias/planos
    ("placasteste01", "Placas.teste", triagem.SEGMENTO),
    ("grupoxyz_teste", "Grupo XYZ", triagem.COMERCIAL),
    ("hms_teste", "HMS inox", triagem.COMERCIAL),
    ("complexoteste", "Complexo Teste", triagem.COMERCIAL),
    ("guilherme.teste", "Guilherme | Consultor Comercial", triagem.PROFISSIONAL),
    ("dra.ana.teste", "Ana Teste", triagem.PROFISSIONAL),
    ("ossel.testeagora", "OSSEL Teste Agora", triagem.INDEFINIDO),
    ("maria.souza.teste", "Maria Souza", triagem.PESSOA),
    ("joao_pereira89", "", triagem.PESSOA),
    ("mariaclarateste", "", triagem.PESSOA),
])
def test_prioridades(usuario, nome, esperado):
    assert triagem.avaliar(Perfil(usuario=usuario, nome=nome, privado=False))[0] == esperado


def test_privado_vai_para_o_fim_e_nao_e_lido():
    pr, _ = triagem.avaliar(Perfil(usuario="teste_funerariax", privado=True))
    assert pr == triagem.PRIVADO and not triagem.deve_ler(pr, "todos")


def test_modos():
    assert triagem.deve_ler(triagem.INDEFINIDO, "candidatos") and not triagem.deve_ler(triagem.PESSOA, "candidatos")
    assert triagem.deve_ler(triagem.PESSOA, "todos") and not triagem.deve_ler(triagem.SEGMENTO, "nenhum")


def test_nome_de_pessoa_nao_e_descartado_so_ordenado():
    # profissional autônomo com nome de pessoa: lido no modo "todos"; no "candidatos" fica sem leitura, mas é registrado
    pr, _ = triagem.avaliar(Perfil(usuario="carlos.teste", nome="Carlos Teste"))
    assert pr == triagem.PESSOA and triagem.deve_ler(pr, "todos")


def test_criterios_configuraveis(tmp_path, monkeypatch):
    arq = tmp_path / "triagem.json"
    arq.write_text(json.dumps({"ler_ate_prioridade": {"candidatos": 4}, "palavras_comerciais_extras": ["velatorio"],
                               "prenomes_extras": ["zorbek"], "excluir_usuarios_regex": "^fake",
                               "publicacoes": {"motivos": ["duvidoso"]}}), encoding="utf-8")
    monkeypatch.setenv("PROSPECCAO_TRIAGEM", str(arq))
    cfg = triagem.carregar_config()
    assert triagem.deve_ler(triagem.PESSOA, "candidatos", cfg)
    assert triagem.avaliar(Perfil(usuario="teste_x1", nome="Velatorio Teste"), cfg)[0] in (triagem.SEGMENTO, triagem.COMERCIAL)
    assert triagem.avaliar(Perfil(usuario="zorbek.teste", nome="Zorbek Teste"), cfg)[0] == triagem.PESSOA
    assert triagem.avaliar(Perfil(usuario="fake_funeraria", nome=""), cfg)[0] == triagem.PRIVADO
    assert cfg["publicacoes"]["motivos"] == ["duvidoso"] and cfg["publicacoes"]["quantidade"] == 12


def test_triagem_json_invalido(tmp_path, monkeypatch):
    arq = tmp_path / "triagem.json"
    arq.write_text("{ruim", encoding="utf-8")
    monkeypatch.setenv("PROSPECCAO_TRIAGEM", str(arq))
    with pytest.raises(ValueError):
        triagem.carregar_config()
