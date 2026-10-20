"""Dados não confirmados, categoria, horário, seguidores e avaliação."""

from empresas import categorias, extrair
from empresas.entradas import Entrada
from empresas.exportar import NAO_CONFIRMADO, celula, linha_planilha
from empresas.pesquisa import Registro, _finalizar, campos_nao_confirmados


def _registro():
    return Registro(Entrada(linha=1, original="Teste", nome="Teste"))


def test_seguidores():
    assert extrair.seguidores_em("Bauducco (@bauducco) 584K Followers, 195 Following") == 584_000
    assert extrair.seguidores_em("1,791 Followers, 3,755 Following") == 1791
    assert extrair.seguidores_em("5M seguidores") == 5_000_000
    assert extrair.seguidores_em("714 mil seguidores") == 714_000
    assert extrair.seguidores_em("1,2 mi seguidores") == 1_200_000
    assert extrair.seguidores_em("sem contador") is None


def test_horarios_em_texto():
    t = "Segunda a sábado: 11h40 às 22h Domingos e feriados: 11h40 às 16h Rua Pedro de Toledo, 450"
    assert extrair.horarios_em(t) == ["Segunda a sábado: 11h40 às 22h; Domingos e feriados: 11h40 às 16h"]
    assert extrair.horarios_em("Seg-Sex 08:00 - 18:00 | Sáb 08:00 - 12:00") == ["Seg-Sex 08:00 - 18:00; Sáb 08:00 - 12:00"]
    assert extrair.horarios_em("Fundada em 1894, a confeitaria tem 3 andares e 120 lugares") == []


def test_horario_e_avaliacao_jsonld():
    org = {"@type": "Bakery", "openingHoursSpecification": [
        {"dayOfWeek": ["https://schema.org/Monday", "Tuesday"], "opens": "07:00:00", "closes": "20:00:00"}],
        "aggregateRating": {"ratingValue": "4.7", "reviewCount": 312}}
    assert extrair.horario_jsonld(org) == "seg/ter 07:00–20:00"
    assert extrair.horario_jsonld({"openingHours": "Mo-Fr 08:00-18:00"}) == "Mo-Fr 08:00-18:00"
    assert extrair.avaliacao_jsonld(org) == "4.7 de 5 (312 avaliações)"


def test_cnae_vira_segmento_a_m():
    """O CNAE só interessa quando aponta para um dos 13 segmentos de parceiros; o resto fica sem segmento."""
    assert categorias.de_cnae("9603305 - Serviços de funerárias") == "F"
    assert categorias.de_cnae("9603301 - Gestão e manutenção de cemitérios") == "C"
    assert categorias.de_cnae("4789002 - Comércio varejista de plantas e flores naturais") == "D"
    assert categorias.de_cnae("4789004 - Comércio varejista de animais vivos") == "I"
    assert categorias.de_cnae("7500100 - Atividades veterinárias") == "H"
    assert categorias.de_cnae("6511102 - Planos de auxílio-funeral") == "G"
    assert categorias.de_cnae("9491000 - Organizações religiosas") == "J"
    assert categorias.de_cnae("") == ""
    # Fora dos 13 segmentos: nada. (Era aqui que saíam "Restaurante", "Mercearia", "Odontologia"...)
    for fora in ("5611201 - Restaurantes e similares", "4712100 - Mercearias", "4721102 - Padaria",
                 "8630504 - Atividade odontológica", "6462000 - Holdings"):
        assert categorias.de_cnae(fora) == "", fora


def test_segmento_pelo_site_e_pelo_nome():
    assert categorias.de_schema(["LocalBusiness", "FuneralHome"]) == "F"
    assert categorias.de_schema(["Bakery"]) == ""          # padaria não é segmento nosso
    assert categorias.por_palavras("Luto Curitiba | Plano Funerário") in ("F", "G")
    assert categorias.por_palavras("Floricultura Bela Flor") == "D"
    assert categorias.por_palavras("Empresa XYZ Participações") == ""
    assert categorias.por_palavras("Restaurante da Dona Maria") == ""


def test_rotulo_e_volta():
    assert categorias.rotulo("F") == "F · Crematórios e funerárias humanas"
    assert categorias.codigo_de_rotulo("F · Crematórios e funerárias humanas") == "F"
    assert categorias.codigo_de_rotulo("F") == "F"
    assert categorias.codigo_de_rotulo("Padaria") == ""
    assert categorias.codigo_de_rotulo("") == ""


def test_jsonld_de_qualquer_empresa_continua_sendo_lido():
    """O extrator precisa achar o bloco da empresa mesmo quando ela não é de nenhum dos 13 segmentos:
    é de lá que saem telefone, endereço e horário."""
    assert categorias.e_organizacao("Bakery")
    assert categorias.e_organizacao(["LocalBusiness", "Restaurant"])
    assert categorias.e_organizacao("FuneralHome")
    assert categorias.e_organizacao("ShoeStore")
    assert not categorias.e_organizacao("BreadcrumbList")
    assert not categorias.e_organizacao(["WebPage", "Article"])


def test_valor_confirmado_tem_prioridade():
    r = _registro()
    r.add("instagram", "https://www.instagram.com/homonimo/", "busca1", "busca", confirmado=False)
    r.add("instagram", "https://www.instagram.com/oficial/", "https://site.com.br/", "site")
    assert r.valor("instagram") == "https://www.instagram.com/oficial/"
    assert r.confirmado("instagram")
    assert r.valor("site", so_confirmado=True) == ""


def test_dados_nao_confirmados_aparecem_marcados():
    r = _registro()
    r.add("cnpj", "11.222.333/0001-81", "https://api", "cadastro", confirmado=False)
    r.add("telefones", "(41) 3333-4444", "https://site.com.br/", "site")
    r.add("telefones", "(41) 99999-0000", "https://instagram.com/x/", "instagram", confirmado=False)
    r.add("seguidores_instagram", "1500", "https://instagram.com/x/", "instagram", confirmado=False)
    _finalizar(r)
    assert r.d["status"] == "provavel" and r.d["confianca"] == "baixa"
    assert set(campos_nao_confirmados(r)) == {"cnpj", "telefones", "seguidores_instagram"}

    texto, nao, bruto = celula(r.d, "telefones")
    assert texto == "(41) 3333-4444 | (41) 99999-0000" + NAO_CONFIRMADO and nao
    texto, nao, bruto = celula(r.d, "cnpj")
    assert texto == "11.222.333/0001-81" + NAO_CONFIRMADO and bruto == "11.222.333/0001-81"
    l = linha_planilha(r.d)
    assert "CNPJ" in l["nao_confirmados"] and "Telefones" in l["nao_confirmados"]


def test_confirmar_depois_promove_o_valor():
    r = _registro()
    r.add("site", "https://x.com.br/", "https://busca", "busca", confirmado=False)
    _finalizar(r)
    assert r.d["status"] == "parcial" and r.d["confianca"] == "baixa"
    r.add("site", "https://x.com.br/", "https://prova", "revisao", True)
    _finalizar(r)
    assert r.confirmado("site") and r.d["confianca"] == "media" and "site" not in r.d["nao_confirmados"]


def test_valor_confirmado_por_outra_fonte_deixa_de_ser_nao_confirmado():
    r = _registro()
    r.add("telefones", "(14) 3222-0000", "https://a", "busca", confirmado=False)
    r.add("telefones", "(14) 3222-0000", "https://b", "revisao", True)
    _finalizar(r)
    assert "telefones" not in r.d["nao_confirmados"]
    assert celula(r.d, "telefones")[:2] == ("(14) 3222-0000", False)


def test_endereco_completo_e_registro_antigo_sem_flag():
    r = _registro()
    for campo, v in (("endereco", "Rua X, 10"), ("bairro", "Centro"), ("cidade", "Curitiba"), ("uf", "PR"), ("cep", "80010-130")):
        r.d["campos"][campo] = [{"valor": v, "fonte": "f", "origem": "cadastro"}]  # formato de lotes antigos
    l = linha_planilha(r.d)
    assert l["endereco_completo"] == "Rua X, 10 - Centro, Curitiba/PR, CEP 80010-130"
    assert not l["_nao_confirmados"]


def test_dominio_precisa_de_termo_distintivo():
    from empresas.pesquisa import _pontuar_dominio
    assert _pontuar_dominio("Cemitério Parque Iguaçu", "https://cemiterio.net.br/") < 80   # portal do segmento
    assert _pontuar_dominio("Padaria Benjamin Abrahão", "https://padaria.net.br/") < 80
    assert _pontuar_dominio("Cemitério Parque Iguaçu", "https://parqueiguacu.com.br/") >= 80
    assert _pontuar_dominio("Livraria da Vila", "https://livrariadavila.com.br/") >= 80
    assert _pontuar_dominio("Drogaria Araujo", "https://www.araujo.com.br/") >= 80


def test_categorias_relacionadas():
    """Com segmentos, 'relacionadas' é simplesmente ser o mesmo segmento (aceita a letra ou o rótulo)."""
    assert categorias.relacionadas("F", "F · Crematórios e funerárias humanas")
    assert categorias.relacionadas("D · Floriculturas", "D")
    assert not categorias.relacionadas("D · Floriculturas", "F · Crematórios e funerárias humanas")
    assert not categorias.relacionadas("", "F")
