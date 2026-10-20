"""Regressões da auditoria da análise REAL de 1.000 seguidores (19/10/2026), recriadas com DADOS DE TESTE FICTÍCIOS,
e regras de publicações/locais/destaques."""

import re

import pytest

from prospeccao.classificar import classificar, precisa_publicacoes
from prospeccao.perfis import Perfil


def _p(usuario, nome="", bio="", cat_ig="", comercial=True, privado=False):
    return Perfil(usuario=usuario, nome=nome, bio=bio, categoria_ig=cat_ig, conta_comercial=comercial, privado=privado,
                  detalhes="perfil")


def _post(texto, fixado=False, local="", hashtags=None):
    return {"texto": texto, "hashtags": hashtags if hashtags is not None else re.findall(r"#(\w+)", texto), "fixado": fixado,
            "local": local, "data": 0, "codigo": ""}


def _fortes(r):
    return {c["codigo"] for c in r["categorias"] if c["confianca"] != "baixa"}


# ---------- perfis reais que eram falsos positivos

def test_mencao_a_outra_conta_nao_e_evidencia():
    r = classificar(_p("teste_douglas", "Douglas Teste", "Casado com @teste_kamiladafuneraria / Pai do Teste / @teste_funeraria.x", comercial=None))
    assert not _fortes(r) and any(s.startswith("menciona") for s in r["sinais"])
    r = classificar(_p("teste_andre", "André Teste", "Meu feed / @teste_casa.igreja", comercial=None))
    assert "J" not in {c["codigo"] for c in r["categorias"]}


@pytest.mark.parametrize("bio", [
    "💍 Casada / 📍Brumadinho / ▪️Agente Funerária",
    "@teste_esposa / papai❤️ / agente funerário",
    "homem de fé / Agente funerário Mirim⚰️",
    "Sou agente Funerário / Curto anime e esportes",
    "estudo na faculdade tanatopraxia e necropsia",
    "cursando auxiliar de necropsia 🎓",
])
def test_pessoa_fisica_do_setor_nao_e_empresa_confirmada(bio):
    r = classificar(_p("teste_pessoa_setor", "Fulana Teste", bio, comercial=None))
    assert r["situacao"] in ("revisar", "sem_correspondencia") and not _fortes(r), r


def test_anos_de_mercado_nao_e_idade():
    r = classificar(_p("teste_funerariagoiania", "Funerária Teste", "A mais de 30 anos no mercado cuidando da sua família. "
                       "WhatsApp 62 99999-0000", "Serviços funerários e cemitério"))
    assert r["tipo_perfil"] != "pessoal" and r["situacao"] == "identificado"


def test_religiao_pessoal_nao_e_igreja():
    r = classificar(_p("teste_camila", "Camila Teste", '"Deus cuida de cada detalhe." / Católica / Casada e Mãe', "Blog pessoal"))
    assert "J" not in _fortes(r)
    r = classificar(_p("teste_comunidade", "Comunidade Teste", "Comunidade católica · missas aos domingos"))
    assert "J" in _fortes(r)


def test_santuario_de_decoracao_nao_e_igreja():
    r = classificar(_p("teste_decor", "Teste Memories", "Centros florales y santuarios, altares portátiles (funeral, sepelio, luto)"))
    assert "J" not in _fortes(r) and "F" in _fortes(r)


def test_fornecedor_do_setor_fica_identificado_com_ressalva():
    r = classificar(_p("teste_sistemas", "Teste Sistemas", "Sistemas de gestão para funerárias · agende uma demonstração"))
    f = next(c for c in r["categorias"] if c["codigo"] == "F")
    assert f["confianca"] == "media" and "setor" in f.get("limitacao", "")


# ---------- empresas reais que eram falsos negativos

@pytest.mark.parametrize("usuario,nome,bio,cod", [
    ("teste_sepelios", "Sepelios Teste", "En ese momento difícil, estamos para ayudarte. Nos ocupamos de todo", "F"),
    ("teste_ataudes", "Ataudes Teste", "Ataúdes de calidad · Fabricación", "F"),
    ("teste_urnas", "Urnas Teste", "Fabricantes de urnas en maderas nobles · cotiza por WhatsApp", "F"),
    ("teste_cremations", "Teste Cremations LLC", "We sell cremation urns at an affordable price", "F"),
    ("teste_burial", "Teste Repatriation", "Repatriation. Burial. Cremation. 24h", "F"),
    ("teste_dagma", "Teste equipamentos funerários", "Tecnologia para o serviço", "F"),
    ("teste_arte", "Teste Artes Plásticas", "Arte Sacra · Arte Tumular · Monumentos · envio nacional", "A"),
    ("teste_qr", "Teste Memorial QR", "Memorial afetivo por QR Code · memórias para sempre", "A"),
    ("teste_placaspersonalizadas", "Placas.teste", "Placas personalizadas para homenagear quem você ama", "A"),
    ("teste_cementerio", "Teste Parque", "Cementerio parque y crematorio", "C"),
])
def test_vocabulario_espanhol_ingles_e_termos_novos(usuario, nome, bio, cod):
    assert cod in _fortes(classificar(_p(usuario, nome, bio)))


def test_criador_de_conteudo_do_tema_vai_para_revisao():
    r = classificar(_p("teste_tanato_criador", "Teste | Tanatopraxista", "🎥 criador de conteúdo fúnebre / tanatopraxista / curiosidades",
                       "Criador(a) de conteúdo digital", comercial=False))
    assert r["situacao"] == "revisar" and not _fortes(r)
    # empresa que usa a mesma categoria do Instagram, mas tem sinal comercial forte, continua identificada
    r = classificar(_p("teste_funeraria_criadora", "Funerária Teste", "Plano Familiar por R$20/mês · Av. Teste, 100 · Ligue 24h",
                       "Criador(a) de conteúdo digital"))
    assert r["situacao"] == "identificado"


def test_industria_de_coroas_e_floricultura():
    assert "D" in _fortes(classificar(_p("teste_coroas", "", "Indústria de Coroas Teste há mais de 30 anos atendendo todo o Brasil",
                                         "Serviços funerários e cemitério")))


def test_anos_no_setor_funerario_nao_e_fornecedor():
    r = classificar(_p("teste_sepelios2", "Sepelios Teste", "62 años en el sector funerario. Atención profesional. 📍Calle Teste 1790"))
    f = next(c for c in r["categorias"] if c["codigo"] == "F")
    assert "setor" not in (f.get("limitacao") or "")


def test_funeraria_e_crematorio_pet_e_so_pet():
    r = classificar(_p("teste_realizepet", "Teste Pet - Funerária Pet 24h", "Funerária & Crematório Pet • 24h · despedidas com respeito"))
    assert _fortes(r) == {"E"}


def test_musicoterapeuta_do_luto_e_m():
    assert "M" in _fortes(classificar(_p("teste_mt", "Teste | Musicoterapeuta", "Luto materno-parental · acolhimento")))


# ---------- publicações, locais e destaques

def test_empresa_so_com_informacao_nas_publicacoes():
    p = _p("teste_grupoxyz", "Grupo XYZ", "Fale conosco", "Produto/serviço")
    assert classificar(p)["situacao"] == "sem_correspondencia"
    p.posts = [_post("Nosso plano funerário cobre toda a família #planofunerario"), _post("Plano funerário a partir de R$ 30")]
    r = classificar(p)
    g = next(c for c in r["categorias"] if c["codigo"] == "G")
    assert r["situacao"] == "identificado" and g["confianca"] == "media" and g["limitacao"] == "evidência só nas publicações"
    assert any("2 publicações" in e for e in g["evidencias"]) and any("publicações" in f for f in r["fontes"])


def test_um_post_isolado_e_so_indicio_mas_fixado_vale():
    p = _p("teste_loja", "Loja Teste", "Atendimento e vendas")
    p.posts = [_post("Hoje fomos ao velório de um amigo, muita saudade"), _post("Promoção de verão")]
    assert classificar(p)["situacao"] != "identificado"
    p.posts = [_post("Coroas de flores para velório com entrega 24h", fixado=True), _post("Promoção de verão")]
    r = classificar(p)
    assert "D" in _fortes(r) and any("fixada" in e for c in r["categorias"] for e in c["evidencias"])


def test_hashtags_ambiguas_nao_confirmam():
    p = _p("teste_padaria", "Padaria Teste", "Pães e doces · delivery")
    p.posts = [_post("Bom dia! #pet #flores #luto"), _post("Café quentinho #flores")]
    assert classificar(p)["situacao"] != "identificado"


def test_mencao_nas_legendas_nao_conta():
    p = _p("teste_fotografo", "Fotógrafo Teste", "Fotos e vídeos")
    p.posts = [_post("Obrigado @teste_funerariax pela parceria"), _post("Evento com @teste_funerariax")]
    assert "F" not in _fortes(classificar(p))


def test_local_do_proprio_perfil_vale_local_visitado_nao():
    p = _p("teste_placarte", "Placas Placarte Teste", "Enviamos para todo o Brasil")
    p.posts = [_post("Nosso trabalho", local="Marmoraria Placarte Mármores e Granitos")]
    assert "A" in _fortes(classificar(p))
    q = _p("teste_viajante", "Viajante Teste", "Fotos de viagem", comercial=None)
    q.posts = [_post("Que lugar bonito", local="Cemitério da Consolação")]
    assert classificar(q)["situacao"] == "sem_correspondencia"


def test_pagina_que_so_fala_do_tema_nao_vira_empresa():
    # caso real: página de lendas urbanas com várias legendas sobre cemitérios e lápides, sem oferecer serviço
    p = _p("teste_lendasdeplantao", "Teste Lendas de Plantão", "Lendas urbanas e do folclore. Venha levar sustos com a gente!")
    p.posts = [_post("A noiva do cemitério apareceu perto da lápide. Relatos reais no Lendas de Plantão"),
               _post("Um causo no cemitério velho: ela já não estava neste plano"),
               _post("Ninguém sabia de quem era aquela lápide no cemitério")]
    r = classificar(p)
    assert r["situacao"] != "identificado" and not _fortes(r)
    assert any("não oferecem o serviço" in (c.get("limitacao") or "") for c in r["categorias"])


def test_traslado_de_aeroporto_nao_e_funerario():
    p = _p("teste_maggiotraslados", "", "")
    p.posts = [_post("", local="Aeropuerto Internacional Teste")]
    assert "F" not in {c["codigo"] for c in classificar(p)["categorias"]}
    q = _p("teste_traslados", "Teste Traslados", "Traslado de corpos e repatriação funerária 24h")
    assert "F" in _fortes(classificar(q))


def test_destaques_contribuem():
    p = _p("teste_grupoabc", "Grupo ABC", "Fale conosco", "Produto/serviço")
    p.destaques = ["Planos funerários", "Unidades", "Coroas de flores"]
    assert {"G", "D"} <= _fortes(classificar(p))


def test_publicacoes_ausentes_ou_vazias_nao_quebram():
    p = _p("teste_vazio", "Teste", "")
    p.posts = [{"texto": None, "hashtags": None, "fixado": False, "local": None}]
    p.destaques = []
    assert classificar(p)["situacao"] == "sem_correspondencia"


def test_quem_precisa_da_etapa_de_publicacoes():
    def caso(campos, **extra):
        perfil = Perfil(**{"usuario": "teste_x", "detalhes": "perfil", "privado": False, **campos})
        motivo = precisa_publicacoes(dict(perfil.para_dict(), **extra), classificar(perfil))
        return motivo[1] if motivo else None

    assert caso({"bio": "Fale conosco", "categoria_ig": "Produto/serviço", "conta_comercial": True}).startswith("conta comercial")
    assert caso({"nome": "Funerária Teste", "bio": "Funerária 24h", "categoria_ig": "Serviços funerários e cemitério"}) is None
    assert caso({"bio": "", "privado": True}) is None
    assert caso({"bio": "Casada 💍 mãe de 2"}) is None
    assert caso({"bio": "Fale conosco", "conta_comercial": True, "etapas": ["lista", "perfil", "publicacoes"]}) is None
    assert caso({"nome": "Pax Teste", "bio": ""}, triagem={"prioridade": 0}).startswith("bio vazia")
    assert caso({"nome": "Fulano", "bio": ""}, triagem={"prioridade": 3}) is None  # bio vazia de nome indefinido: não gasta
