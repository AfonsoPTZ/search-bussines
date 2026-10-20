from empresas import cnpj, entradas, extrair
from empresas.util import similaridade


def test_cnpj_numerico():
    assert cnpj.valido("00.000.000/0001-91")
    assert cnpj.valido("33014556000196")
    assert not cnpj.valido("33014556000197")
    assert not cnpj.valido("11111111111111")
    assert cnpj.formatar("33014556000196") == "33.014.556/0001-96"


def test_cnpj_alfanumerico():
    # Exemplo oficial da Receita Federal para o CNPJ alfanumérico
    assert cnpj.valido("12.ABC.345/01DE-35")
    assert not cnpj.valido("12.ABC.345/01DE-36")


def test_encontrar_cnpj_em_texto():
    texto = "Razão: X LTDA - CNPJ 33.014.556/0001-96. Tel (21) 2206-6708 https://cnpj.biz/00000000000191"
    assert cnpj.encontrar(texto) == ["33014556000196", "00000000000191"]
    assert cnpj.encontrar("pedido 12345678901234") == []  # 14 dígitos com DV inválido


def test_telefones():
    t = "Ligue (14) 3222-1234 ou 14 99876-5432, +55 11 3333 4444. SAC 0800 123 4567. CEP 17010-100"
    assert extrair.telefones_em(t) == ["(14) 3222-1234", "(14) 99876-5432", "(11) 3333-4444", "0800 123 4567"]
    assert extrair.ceps_em(t) == ["17010-100"]
    assert extrair.ceps_em("Botafogo, Rio de Janeiro/RJ - CEP 22.270-000") == ["22270-000"]


def test_email_de_credito_do_site_e_ignorado():
    t = "Contato: reservas@cantina.com.br\n© 2022 Empório Ltda. Website design by Al Hupert alhupert@gmail.com"
    assert extrair.emails_em(t) == ["reservas@cantina.com.br"]


def test_links_html():
    html = """<html><head><title>Padaria Real | Bauru</title>
    <script type="application/ld+json">{"@type":"Bakery","name":"Padaria Real","telephone":"+55 14 3222-1234",
    "address":{"streetAddress":"Rua X, 10","addressLocality":"Bauru","addressRegion":"SP","postalCode":"17010-100"}}</script>
    </head><body>
    <a href="https://wa.me/5514998765432">WhatsApp</a>
    <a href="https://www.instagram.com/padariareal/">IG</a>
    <a href="https://www.instagram.com/p/abc123/">post</a>
    <a href="https://www.facebook.com/sharer.php?u=x">share</a>
    <a href="mailto:contato@padariareal.com.br">email</a>
    <a href="/contato">Fale conosco</a>
    <p>CNPJ: 33.014.556/0001-96</p></body></html>"""
    a, meta = extrair.de_html(html, "https://www.padariareal.com.br/")
    assert a.whatsapp == ["(14) 99876-5432"]
    assert a.instagram == ["https://www.instagram.com/padariareal/"]
    assert a.facebook == []
    assert a.emails == ["contato@padariareal.com.br"]
    assert "(14) 3222-1234" in a.telefones
    assert a.cnpjs == ["33014556000196"]
    assert extrair.endereco_jsonld(a.jsonld[0])["cidade"] == "Bauru"
    assert meta["links_internos"][0][0] == "https://www.padariareal.com.br/contato"


def test_entradas():
    e = entradas.de_linha("@padariareal", 1)
    assert e.tipo == "instagram" and e.instagram == "padariareal"
    e = entradas.de_linha("https://www.instagram.com/Cacau.Show/?hl=pt", 2)
    assert e.instagram == "cacau.show"
    e = entradas.de_linha("www.empresa.com.br", 3)
    assert e.tipo == "site" and e.site == "https://www.empresa.com.br"
    e = entradas.de_linha("33.014.556/0001-96", 4)
    assert e.tipo == "cnpj"
    e = entradas.de_linha("- Padaria Real | Bauru/SP | @padariareal", 5)
    assert (e.nome, e.cidade, e.uf, e.instagram) == ("Padaria Real", "Bauru", "SP", "padariareal")
    e = entradas.de_linha("Padaria Real; Bauru", 6)
    assert e.cidade == "Bauru"
    assert entradas.de_linha("# comentário", 7) is None


def test_similaridade_ignora_termos_societarios():
    assert similaridade("Padaria Real", "PADARIA REAL LTDA ME") >= 95
    assert similaridade("Cacau Show", "Chocolates Garoto S.A.") < 60


def test_rua_para_comparar_enderecos():
    from empresas.pesquisa import _rua
    assert _rua("Rua Haddock Lobo, 354 - Jardins") == "haddock lobo"
    assert _rua("Rua Haddock Lobo, 328") == "haddock lobo"
    assert _rua("Avenida Paulista 2073, loja 1") == "paulista"


def test_loja_franqueada_nao_e_nome_identico():
    from empresas.util import contido_com_extras
    assert similaridade("Kopenhagen", "KOPENHAGEN MARIO FERRAZ") < 85
    assert contido_com_extras("Kopenhagen", "KOPENHAGEN MARIO FERRAZ")
    assert not contido_com_extras("Havan", "HAVAN S.A")
