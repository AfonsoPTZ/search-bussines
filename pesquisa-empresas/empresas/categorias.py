"""Segmento da empresa dentro das 13 categorias de parceiros do RIP Memorial (A–M).

Este projeto só prospecta esses 13 segmentos. Uma empresa que não é de nenhum deles (padaria, restaurante,
mercearia...) fica **sem segmento** — e é isso que deve aparecer, em vez de uma categoria comercial genérica
que não tem uso nenhum aqui.

A definição dos segmentos é única e mora em `prospeccao.categorias` (a mesma usada para classificar os perfis
do Instagram). Aqui só traduzimos para ela as três evidências que a pesquisa de empresas consegue obter:

  1. CNAE do cadastro da Receita  -> `de_cnae`   (dado estruturado; a evidência mais forte)
  2. tipo schema.org do site      -> `de_schema`
  3. nome e textos do site        -> `por_palavras` (as regras A–M aplicadas ao texto; só indício)

O valor gravado no campo `categoria` do registro é o rótulo legível ("F · Crematórios e funerárias humanas"),
e `codigo_de_rotulo` devolve a letra de volta.
"""

import re

from prospeccao.categorias import CODIGOS, POR_CODIGO

__all__ = ["CODIGOS", "POR_CODIGO", "rotulo", "codigo_de_rotulo", "de_cnae", "de_schema", "e_organizacao",
           "por_palavras", "relacionadas"]


def rotulo(codigo: str) -> str:
    """'F' -> 'F · Crematórios e funerárias humanas'"""
    c = POR_CODIGO.get((codigo or "").upper())
    return f"{c.codigo} · {c.nome}" if c else ""


def codigo_de_rotulo(valor: str | None) -> str:
    """'F · Crematórios e funerárias humanas' -> 'F' (aceita também só a letra)."""
    v = (valor or "").strip().upper()
    if v in POR_CODIGO:
        return v
    cod = v.split("·")[0].strip().split(" ")[0].strip()
    return cod if cod in POR_CODIGO else ""


# ------------------------------------------------------------------------------------------------ CNAE
# Prefixo do código CNAE (só dígitos) -> segmento. Vale o prefixo mais longo que casar.
# Só entram os CNAEs que realmente indicam um dos 13 segmentos: o resto da economia não interessa aqui.
_CNAE = {
    # A. Placas, lápides e fotoporcelana (marmorarias e trabalhos em pedra/bronze funerário)
    "2391": "A",            # aparelhamento de placas e execução de trabalhos em mármore, granito, ardósia
    "2399": "A",            # outros produtos de minerais não metálicos
    # C. Cemitérios  /  F. Crematórios e funerárias humanas  (a divisão 9603 separa os dois)
    "9603301": "C",         # gestão e manutenção de cemitérios
    "9603302": "F",         # serviços de cremação
    "9603303": "F",         # serviços de sepultamento
    "9603304": "F",         # serviços de somatoconservação
    "9603305": "F",         # serviços de funerárias
    "9603": "F",            # demais atividades funerárias
    # D. Floriculturas
    "0122": "D",            # cultivo de flores e plantas ornamentais
    "4789002": "D",         # comércio varejista de plantas e flores naturais
    "4616802": "D",         # representantes comerciais de flores e plantas
    # G. Seguro de vida e planos funerários
    "6511": "G",            # seguros de vida
    "6511102": "G",         # planos de auxílio-funeral
    "6530": "G",            # previdência complementar
    "6622": "G",            # corretores e agentes de seguros
    # H. Clínicas e hospitais veterinários
    "7500": "H",            # atividades veterinárias
    # I. Pet shops e serviços pet
    "4789004": "I",         # animais vivos, artigos e alimentos para animais de estimação
    "4623108": "I",         # atacado de alimentos para animais
    "9609208": "I",         # higiene e embelezamento de animais domésticos
    # J. Igrejas e comunidades religiosas
    "9491": "J",            # organizações religiosas ou filosóficas
    # K. Hospitais e cuidados paliativos
    "8610": "K",            # atividades de atendimento hospitalar
    "8711": "K",            # atendimento em residências (idosos, cuidados prolongados)
    "8712": "K",            # atividades de fornecimento de infraestrutura de apoio ao paciente (home care)
    "8730": "K",            # assistência social com alojamento
    # M. Psicólogos e terapeutas do luto
    "8650003": "M",         # atividades de psicologia e psicanálise
}


def de_cnae(cnae: str | None) -> str:
    """'9603-3/05 - Serviços de funerárias' -> 'F'. Fora dos 13 segmentos, devolve ''."""
    codigo = re.sub(r"\D", "", (cnae or "").split(" - ")[0])
    for n in (7, 4, 3, 2):
        if len(codigo) >= n and codigo[:n] in _CNAE:
            return _CNAE[codigo[:n]]
    return ""


# ------------------------------------------------------------------------------------------------ schema.org
# Tipo declarado no próprio site que corresponde a um dos 13 segmentos.
_SCHEMA = {
    "FuneralHome": "F", "Crematorium": "F", "Mortuary": "F",
    "Cemetery": "C",
    "Florist": "D",
    "VeterinaryCare": "H",
    "PetStore": "I", "AnimalShelter": "I",
    "InsuranceAgency": "G",
    "Church": "J", "PlaceOfWorship": "J", "HinduTemple": "J", "Mosque": "J", "Synagogue": "J", "BuddhistTemple": "J",
    "CatholicChurch": "J",
    "Hospital": "K", "MedicalClinic": "K", "Hospice": "K",
    "Psychologist": "M",
}

# Tipos schema.org que apenas indicam "isto é uma organização/negócio" — usados pelo extrator para achar o bloco
# JSON-LD da empresa no site (de onde saem telefone, endereço, horário). NÃO dizem nada sobre o segmento: aqui
# interessa qualquer empresa, porque é dela que vamos tirar os contatos.
_ORGANIZACAO = {
    "Organization", "Corporation", "LocalBusiness", "Store", "FoodEstablishment", "ProfessionalService",
    "HealthAndBeautyBusiness", "HomeAndConstructionBusiness", "AutomotiveBusiness", "EntertainmentBusiness",
    "FinancialService", "LegalService", "RealEstateAgent", "TravelAgency", "EducationalOrganization",
    "SportsActivityLocation", "LodgingBusiness", "NGO", "GovernmentOrganization", "MedicalOrganization",
    "MedicalBusiness", "EmergencyService", "GovernmentOffice", "InternetCafe", "ChildCare", "Dentist", "Physician",
    "Notary", "Attorney", "Electrician", "Plumber", "Locksmith", "MovingCompany", "Resort", "Campground",
}
# Sufixos dos subtipos de LocalBusiness ("Bakery", "ShoeStore", "AutoRepair", "NailSalon"...): o schema.org tem
# dezenas deles e uma lista fixa envelhece mal.
_SUFIXOS_ORG = (
    "Business", "Store", "Shop", "Restaurant", "Service", "Agency", "Clinic", "Market", "Establishment",
    "Organization", "Company", "Dealer", "Salon", "Gym", "School", "Hospital", "Pharmacy", "Hotel", "Station",
    "Center", "Centre", "Office", "Practice", "Care", "Studio", "Bakery", "Brewery", "Winery", "Bar", "Pub",
    "Cafe", "CoffeeShop", "Repair", "Rental", "Lodging", "Spa", "Club", "Library", "Museum", "Theater", "Bank",
)


def de_schema(tipos) -> str:
    """Tipo(s) schema.org do site -> segmento, ou '' se não for um dos 13."""
    for t in tipos if isinstance(tipos, list) else [tipos]:
        if isinstance(t, str) and t in _SCHEMA:
            return _SCHEMA[t]
    return ""


def e_organizacao(tipo) -> bool:
    """O bloco JSON-LD descreve uma empresa/organização? (não diz nada sobre o segmento)"""
    for t in tipo if isinstance(tipo, list) else [tipo]:
        if isinstance(t, str) and (t in _ORGANIZACAO or t in _SCHEMA or t.endswith(_SUFIXOS_ORG)):
            return True
    return False


# ------------------------------------------------------------------------------------------------ texto livre

def por_palavras(texto: str | None) -> str:
    """Segmento sugerido pelo nome/textos do site, pelas MESMAS regras A–M dos perfis do Instagram.

    É só indício: quem grava precisa marcar como não confirmado.
    """
    if not (texto or "").strip():
        return ""
    from prospeccao.classificar import segmentos_de_texto
    achados = segmentos_de_texto("", [texto])
    return achados[0] if achados else ""


def relacionadas(a: str, b: str) -> bool:
    """Dois segmentos falam do mesmo ramo? (com segmentos, é simplesmente ser o mesmo)"""
    return bool(a) and codigo_de_rotulo(a) == codigo_de_rotulo(b)
