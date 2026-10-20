"""Arrobas e classificação. Perfis abaixo são DADOS DE TESTE FICTÍCIOS."""

import pytest

from prospeccao import categorias as cats
from prospeccao.arrobas import ArrobaInvalida, link, normalizar, valida
from prospeccao.classificar import classificar, filtrar, vale_ler_detalhes
from prospeccao.perfis import Perfil, completar, de_lista, normalizar_texto


# ---------- arrobas

@pytest.mark.parametrize("entrada,esperado", [
    ("@FeiraFuneraria", "feirafuneraria"), ("  teste_perfil ", "teste_perfil"), ("@teste.perfil_1", "teste.perfil_1"),
    ("https://www.instagram.com/Teste_Perfil/?hl=pt-br", "teste_perfil"), ("instagram.com/teste.x/", "teste.x"),
    ("www.instagram.com/teste_y", "teste_y"), ('"@teste_z"', "teste_z"),
])
def test_normaliza_arroba(entrada, esperado):
    assert normalizar(entrada) == esperado
    assert valida(entrada)


@pytest.mark.parametrize("entrada", ["", "   ", "@", "teste perfil", ".teste", "teste.", "te..ste", "a" * 31, "teste#1",
                                     "https://instagram.com/", "https://instagram.com/explore/", "@p", "ação"])
def test_rejeita_arroba_invalida(entrada):
    with pytest.raises(ArrobaInvalida):
        normalizar(entrada)
    assert not valida(entrada)


def test_link_do_perfil():
    assert link("teste_x") == "https://www.instagram.com/teste_x/"


# ---------- normalização de perfis e dados ausentes

def test_normalizar_texto_letras_estilizadas_e_acentos():
    assert normalizar_texto("𝐅𝐮𝐧𝐞𝐫á𝐫𝐢𝐚 São José & Cia!") == "funeraria sao jose e cia"
    assert normalizar_texto(None) == ""


def test_de_lista_e_completar_com_campos_ausentes():
    assert de_lista({"full_name": "sem usuario"}) is None
    p = de_lista({"username": "Teste_Sem_Dados", "pk": 123, "full_name": None, "is_private": None})
    assert p.usuario == "teste_sem_dados" and p.pk == "123" and p.nome == "" and p.privado is None
    completar(p, {"biography": None, "category_name": None, "is_business_account": None, "external_url": None,
                  "bio_links": [{"url": "https://teste.example/x"}], "edge_followed_by": {"count": 10}})
    assert p.bio == "" and p.categoria_ig == "" and p.link_externo == "https://teste.example/x" and p.seguidores == 10
    assert p.detalhes == "perfil"
    r = classificar(p)
    assert r["situacao"] == "sem_correspondencia" and r["categorias"] == []


def test_completar_formato_graphql_novo():
    p = Perfil(usuario="teste_pet", pk="9")
    completar(p, {"pk": "9", "full_name": "Teste Pet", "biography": "Banho e tosa", "category": "Pet groomer",
                  "is_business": True, "is_private": False, "follower_count": 50})
    assert p.categoria_ig == "Pet groomer" and p.conta_comercial is True and p.seguidores == 50


# ---------- as 13 categorias

def _p(usuario, nome="", bio="", cat_ig="", comercial=True, privado=False):
    return Perfil(usuario=usuario, nome=nome, bio=bio, categoria_ig=cat_ig, conta_comercial=comercial, privado=privado,
                  detalhes="perfil")


CASOS_13 = [
    ("A", _p("teste_marmoraria_luz", "Marmoraria Luz", "Lápides, túmulos em granito e fotoporcelana. Orçamento sem compromisso")),
    ("B", _p("teste_cemiterio_pet", "Recanto Animal", "Cemitério para animais de estimação · jazigos pet individuais")),
    ("C", _p("teste_parque_da_paz", "Parque da Paz", "Cemitério parque desde 1985. Jazigos e sepultamentos", "Cemetery")),
    ("D", _p("teste_flores_bela", "Flores Bela", "Floricultura · coroas de flores para velório · entregamos 24h", "Florist")),
    ("E", _p("teste_adeus_amigo", "Adeus Amigo", "Crematório pet · cremação individual de animais com entrega das cinzas")),
    ("F", _p("teste_funeraria_central", "Funerária Central", "Serviços funerários 24 horas, velório e cremação",
             "Funeral Service & Cemetery")),
    ("G", _p("teste_protege", "Protege Corretora", "Seguro de vida e plano funerário para toda a família. SUSEP 123", "Insurance Agent")),
    ("H", _p("teste_clinivet", "Clinivet", "Clínica veterinária · plantão 24h · CRMV-SP 1234", "Veterinarian")),
    ("I", _p("teste_petshop_amigo", "Pet Shop Amigo", "Banho e tosa, rações e acessórios. Delivery", "Pet Store")),
    ("J", _p("teste_paroquia_sao_jose", "Paróquia São José", "Missas aos domingos. Pastoral da esperança", "Church")),
    ("K", _p("teste_hospital_esperanca", "Hospital Esperança", "Oncologia e cuidados paliativos", "Hospital")),
    ("L", _p("teste_grupo_acolher", "Instituto Acolher", "Grupo de apoio ao luto · acolhimento a pais enlutados", "Nonprofit organization")),
    ("M", _p("teste_psi_ana", "Ana | Psicóloga", "CRP 06/00000 · Psicologia do luto e perdas · atendimento online", "Psychologist")),
]


@pytest.mark.parametrize("codigo,perfil", CASOS_13, ids=[c for c, _ in CASOS_13])
def test_cada_categoria(codigo, perfil):
    r = classificar(perfil)
    principais = [c["codigo"] for c in r["categorias"] if c["confianca"] in ("alta", "media")]
    assert codigo in principais, r
    assert r["situacao"] == "identificado"
    c = next(c for c in r["categorias"] if c["codigo"] == codigo)
    assert c["evidencias"] and c["nome"] == cats.POR_CODIGO[codigo].nome


def test_categorias_oficiais():
    assert cats.CODIGOS == list("ABCDEFGHIJKLM")
    assert cats.resolver("todas") == cats.CODIGOS == cats.resolver(None) == cats.resolver([])
    assert cats.resolver("c, a") == ["A", "C"]
    with pytest.raises(ValueError):
        cats.resolver("Z")


def test_pet_nao_vira_funeraria_humana_nem_cemiterio_humano():
    r = classificar(_p("teste_crematoriopet", "Crematório Pet Luz", "Crematório de animais. Urnas e homenagens"))
    cods = {c["codigo"] for c in r["categorias"]}
    assert "E" in cods and "F" not in cods
    r = classificar(_p("teste_cemiteriopet", "Cemitério Pet", "Cemitério de animais"))
    cods = {c["codigo"] for c in r["categorias"]}
    assert "B" in cods and "C" not in cods


def test_hospital_veterinario_nao_e_hospital_humano():
    r = classificar(_p("teste_hv", "Hospital Veterinário Teste", "Atendimento 24h"))
    cods = {c["codigo"] for c in r["categorias"]}
    assert "H" in cods and "K" not in cods


def test_perfil_em_mais_de_uma_categoria():
    r = classificar(_p("teste_funeraria_e_planos", "Funerária e Planos Teste", "Funerária 24h · Plano funerário familiar · crematório pet",
                       "Funeral Service & Cemetery"))
    fortes = {c["codigo"] for c in r["categorias"] if c["confianca"] in ("alta", "media")}
    assert {"F", "G", "E"} <= fortes


def test_palavra_isolada_nao_confirma():
    # "flores" sozinho num perfil sem sinal comercial: descartado como ruído
    r = classificar(_p("teste_maria", "Maria", "Amo flores e café", comercial=None))
    assert r["situacao"] == "sem_correspondencia"
    # "pet" sozinho numa conta comercial: no máximo revisão
    r = classificar(_p("teste_loja_x", "Loja X", "Roupas femininas, moda e pets", comercial=True))
    assert r["situacao"] in ("revisar", "sem_correspondencia")
    assert all(c["confianca"] == "baixa" for c in r["categorias"])


def test_estudante_nao_e_clinica():
    r = classificar(_p("teste_ana", "Ana", "Estudante de medicina veterinária 🐶 mãe de pet", comercial=None))
    assert r["situacao"] == "sem_correspondencia", r


def test_psicologo_sem_luto_vai_para_revisao():
    r = classificar(_p("teste_psi_joao", "João Psicólogo", "CRP 01/0000 · ansiedade e depressão", "Psychologist"))
    m = next(c for c in r["categorias"] if c["codigo"] == "M")
    assert m["confianca"] == "baixa" and r["situacao"] == "revisar"


def test_perfil_privado_nunca_confirmado():
    r = classificar(_p("teste_funeraria_priv", "Funerária Teste", "Funerária 24h", comercial=None, privado=True))
    assert r["tipo_perfil"] == "pessoal" and r["situacao"] == "revisar" and r["estado_analise"] == "privado"


def test_so_nome_sem_bio_fica_no_maximo_media():
    p = Perfil(usuario="teste_funerariasaojose", nome="Funerária São José", detalhes="lista")
    r = classificar(p)
    f = next(c for c in r["categorias"] if c["codigo"] == "F")
    assert f["confianca"] == "media" and r["estado_analise"] == "so_nome"


def test_sem_informacao_suficiente():
    for p in (Perfil(usuario="teste_x123"), Perfil(usuario="teste_y", nome=None or "", bio="", detalhes="perfil")):
        r = classificar(p)
        assert r["situacao"] == "sem_correspondencia" and r["categorias"] == []


def test_triagem_para_ler_detalhes():
    assert vale_ler_detalhes(Perfil(usuario="teste_funerariaxyz"))
    assert vale_ler_detalhes(Perfil(usuario="teste_abc", nome="Grupo Vida Eterna"))  # nome empresarial, sem termo do segmento
    assert vale_ler_detalhes(Perfil(usuario="teste_floresdaana"))  # indício fraco
    assert not vale_ler_detalhes(Perfil(usuario="teste_joao_99", nome="João Pereira"))


def test_filtrar_por_categorias_selecionadas():
    r = classificar(CASOS_13[5][1])  # F
    assert filtrar(r, ["A", "B"])["situacao"] == "sem_correspondencia"
    assert filtrar(r, ["F"])["situacao"] == "identificado"


# ---------- regressões vindas da auditoria da prova real (equivalentes FICTÍCIOS)

def test_funeraria_pet_com_categoria_funeraria_do_instagram_nao_vira_humana():
    r = classificar(_p("teste_ultrapetfuneraria", "TestePet | Funerária de Animais",
                       "Despedidas dignas para pets · Cremação e sepultamento com respeito · Atendimento 24h",
                       "Serviços funerários e cemitério"))
    fortes = {c["codigo"] for c in r["categorias"] if c["confianca"] != "baixa"}
    assert fortes == {"E"}


def test_funeraria_com_jazigos_nao_polui_cemiterios():
    r = classificar(_p("teste_funeraria_x", "Funerária Teste", "Sepultamento, jazigos e cremação. Plantão 24h",
                       "Serviços funerários e cemitério"))
    assert "C" not in {c["codigo"] for c in r["categorias"]}


def test_sobrenome_mesquita_nao_e_templo():
    assert classificar(_p("teste_sara.mesquita", "Sara Mesquita", "", comercial=None))["categorias"] == []
    r = classificar(_p("teste_mesquita_central", "Mesquita Central", "Comunidade islâmica · orações de sexta", comercial=None))
    assert "J" in {c["codigo"] for c in r["categorias"]}


def test_placas_de_homenagem_identificadas():
    r = classificar(_p("teste_memorial.placas", "Teste Placas", "Homenagens feitas com amor · Foto, nome e datas · Enviamos para todo o Brasil"))
    a = next(c for c in r["categorias"] if c["codigo"] == "A")
    assert a["confianca"] in ("alta", "media")


def test_cerimonial_de_despedida_e_funerario():
    r = classificar(_p("teste_celebrante", "Teste - Cerimônias Funerais", "Celebrante funeral · cerimoniais de despedidas"))
    assert any(c["codigo"] == "F" and c["confianca"] == "alta" for c in r["categorias"])
