"""As 13 categorias oficiais da prospecção e as regras (palavras-chave e combinações) de cada uma.

Os padrões são expressões regulares aplicadas ao texto normalizado (minúsculas, sem acentos,
pontuação trocada por espaço, '&' trocado por ' e '). Pesos:
    3 = termo específico (ex.: "funerária", "fotoporcelana", "banho e tosa")
    2 = termo forte, mas que aparece em outros contextos (ex.: "marmoraria", "seguros")
    1 = indício fraco (ex.: "flores", "pet", "luto"); sozinho nunca confirma nada

Opções de cada regra:
    composto  - frase combinada (ex.: "crematório pet"); o trecho que ela casa não é reaproveitado pelas
                regras genéricas (assim "crematório pet" não conta também como crematório humano)
    compacto  - padrões procurados no @ e no nome escritos sem espaço (ex.: "funerariasaojose")
    requer    - padrão que precisa aparecer em algum lugar do perfil para a regra valer
    nao_antes - padrão que, logo antes do termo, anula a regra (ex.: "estudante de" veterinária)
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Categoria:
    codigo: str
    nome: str
    descricao: str


CATEGORIAS = [
    Categoria("A", "Placas, lápides e fotoporcelana",
              "Marmorarias, placas funerárias, lápides, fotoporcelana e produtos de identificação e homenagem memorial."),
    Categoria("B", "Cemitérios pet", "Cemitérios para animais, jazigos pet, nichos e sepultamento de animais."),
    Categoria("C", "Cemitérios", "Cemitérios tradicionais, parques cemiteriais, verticais, históricos e administradoras."),
    Categoria("D", "Floriculturas", "Floriculturas, coroas funerárias, arranjos de homenagem e flores para velórios."),
    Categoria("E", "Crematórios e funerárias pet", "Crematórios de animais, funerárias pet, despedida pet, urnas e homenagens pet."),
    Categoria("F", "Crematórios e funerárias humanas", "Crematórios, funerárias e serviços funerários para pessoas."),
    Categoria("G", "Seguro de vida e planos funerários", "Seguradoras de vida, assistência funeral, planos funerários e corretores."),
    Categoria("H", "Clínicas e hospitais veterinários", "Clínicas, hospitais e centros veterinários e médicos veterinários."),
    Categoria("I", "Pet shops e serviços pet", "Pet shops, banho e tosa, hotéis e creches para animais e cuidados pet."),
    Categoria("J", "Igrejas e comunidades religiosas", "Igrejas, paróquias, comunidades e organizações religiosas."),
    Categoria("K", "Hospitais e cuidados paliativos", "Hospitais, clínicas oncológicas, cuidados paliativos e home care."),
    Categoria("L", "Organizações de apoio ao luto", "Associações, grupos e institutos de acolhimento a pessoas enlutadas."),
    Categoria("M", "Psicólogos e terapeutas do luto", "Psicólogos e terapeutas, em especial os que atendem luto e perdas."),
]
POR_CODIGO = {c.codigo: c for c in CATEGORIAS}
CODIGOS = [c.codigo for c in CATEGORIAS]


def resolver(selecao) -> list[str]:
    """'todas' / None / 'A,c' / ['A','C'] -> lista de códigos válidos, na ordem oficial."""
    if selecao is None:
        return list(CODIGOS)
    if isinstance(selecao, str):
        selecao = [s for s in selecao.replace(";", ",").split(",")]
    pedidos = {s.strip().upper() for s in selecao if s and s.strip()}
    if not pedidos or "TODAS" in pedidos or "*" in pedidos:
        return list(CODIGOS)
    invalidos = pedidos - set(CODIGOS)
    if invalidos:
        raise ValueError(f"Categoria(s) desconhecida(s): {', '.join(sorted(invalidos))}. Use A a M ou 'todas'.")
    return [c for c in CODIGOS if c in pedidos]


@dataclass(frozen=True)
class Regra:
    categoria: str
    padrao: str
    peso: int
    composto: bool = False
    compacto: tuple[str, ...] = field(default_factory=tuple)
    requer: str | None = None
    nao_antes: str | None = None


# Contextos reutilizados
PET = (r"(?:pets?|animais|animal|caes|cao|cachorros?|gatos?|caninos?|felinos?|bichos?|dogs?|cats?|mascotas?|"
       r"quatro patas|4 patas|patas|patinhas|focinhos?|doguinhos?|bichinhos?|amigos? de 4 patas)")
_DE = r"(?: (?:de|do|da|dos|das|para|pra|ao|aos|seu|seus|sua|suas|o|os|a|as|for|your|para su|para tu))*"
FUNEBRE = (r"(?:crematorios?|cremac(?:ao|oes)|cremations?|funerarias?|funera(?:l|is)|velorios?|despedidas?|urnas?|urns?|"
           r"cinzas|cenizas|memorial|homenagens?|sepelios?)")
# Encadeado: "funerária e crematório pet", "cremação e urnas para pets"
FUNEBRES = rf"{FUNEBRE}(?: (?:e|ou|y|and|&) {FUNEBRE})*"
# Usado em nao_antes: "estudante de (medicina) veterinária", "apaixonada por flores", "amo meu pet"...
ESTUDANTE = (r"\b(?:estudante|estudo|academic[oa]|futur[oa]|graduand[oa]|alun[oa]|universitari[oa]|curso|cursando|"
             r"faculdade|formand[oa]|estagiari[oa]|apaixonad[oa]|amo|amante|louc[oa]|mae|pai|tutor[a]?|lover)(?: \w+){0,2} $")
PSI = r"(?:psicolog[oa]s?|psicologia|psicoterap(?:ia|euta)s?|psicanalis(?:e|ta)s?|\w*terapeutas?|crp)"
# Fornecedores, sistemas, cursos e mídia QUE ATENDEM o setor funerário (não prestam o serviço final).
SETOR = (r"\b(?:para (?:o )?(?:setor|segmento|ramo|mercado) (?:funerario|memorial)|para (?:as )?funerarias|para (?:agentes )?funerari"
         r"|(?:lideres|empresas|profissionais|empresarios) do (?:setor|segmento|ramo|rubro|sector) (?:funerario|memorial)"
         r"|gestao (?:para|de) funerarias"
         r"|sistemas? (?:de gestao )?(?:para|de) funerarias|cursos? de tanatopraxia|formac(?:ao) (?:profissional )?no setor"
         r"|congresso|congreso|revista|noticias|feiras? (?:funerari\w*|do setor|internaciona\w*)|\w*expo\w*|fabrica de (?:urnas|ataudes|caixoes)"
         r"|fabricantes? de|fabricamos|manufacturer|mayorista|atacado|distribuidora|plataforma|marketing|software"
         r"|sistemas? de gestao|cursos?|treinamentos?|capacitac\w*)\b")
LUTO = r"(?:luto|enlutad[oa]s?|perdas?|tanatolog)"

_R = Regra
REGRAS: list[Regra] = [
    # ---- A. Placas, lápides e fotoporcelana
    _R("A", r"\bfotos? ?(?:em |de |na )?porcelanas?\b|\bfotoceramica\b|\bfotos? (?:em |de )?ceramica\b", 3, True,
       (r"fotoporcelana", r"fotoceramica")),
    _R("A", r"\blapides?\b", 3, compacto=(r"lapide",)),
    _R("A", r"\bplacas? (?:funerarias?|memoria(?:l|is)|de homenagens?|de bronze|em bronze|para tumulos?|para jazigos?|tumulares?|de jazigo|de identificacao|comemorativas?|de inox|em inox|em aco)\b", 3, True,
       (r"placasfunerarias?", r"placasmemoriais", r"placasdebronze")),
    _R("A", r"\bmarmorarias?\b", 2, compacto=(r"marmoraria",)),
    _R("A", r"\bmarmores? e granitos?\b|\bmarmores?\b", 2, compacto=(r"marmores?egranitos?", r"marmore")),
    _R("A", r"\bgranitos?\b", 1),
    _R("A", r"\b(?:tumulos?|jazigos?) (?:em |de )?(?:granito|marmore)\b|\bconstruc(?:ao|oes) de (?:tumulos?|jazigos?)\b|\breforma de (?:tumulos?|jazigos?)\b", 3, True),
    _R("A", r"\btumulos?\b", 2),
    _R("A", r"\b(?:letras|crucifixos?|cruz(?:es)?|vasos?|castical) (?:de|em) (?:bronze|aco inox|inox|latao)\b|\bartigos? em bronze\b|\bbronze funerario\b", 3, True),
    _R("A", r"\bbronzes?\b", 1),
    _R("A", r"\b(?:artefatos?|artigos?|produtos?) (?:funerarios?|cemiteriais?|memoria(?:l|is))\b", 2, True),
    _R("A", r"\bmemoria(?:l|is) personalizad[oa]s?\b|\bplacas? personalizadas?\b|\bplacas?\b", 2, requer=r"tumul|jazig|funer|cemiter|homenag|memorial|saudade|luto|sepult|falecid",
       compacto=(r"placas",)),
    _R("A", r"\barte (?:tumular|cemiterial|funeraria|sacra tumular)\b|\bmonumentos? (?:tumulares?|funerarios?|cemiteriais?)\b|\btumular(?:es)?\b|\bmausoleos?\b|\blapidas?\b|\bmarmolerias?\b|\bheadstones?\b|\bgravestones?\b|\btombstones?\b", 3, True,
       (r"artetumular", r"marmoleria", r"lapida", r"headstone")),
    _R("A", r"\bmemoria(?:l|is) (?:afetivos?|digita(?:l|is)|por qr|online|virtua(?:l|is))\b|\bqr ?code (?:memorial|de homenagem|para tumulos?|para jazigos?)\b|\bhomenagens? digita(?:l|is)\b|\bmemorial pieces\b|\bremembrance\b|\bkeepsakes?\b", 2, True,
       (r"memorialqr", r"qrmemorial")),
    _R("A", r"\beterniz(?:am|ar|e|ando) (?:as )?(?:memorias|quem voce ama|lembrancas)\b|\bmonumentos?\b", 1),

    # ---- B. Cemitérios pet
    _R("B", rf"\bcemiterios?{_DE} {PET}\b|\b{PET} cemiterios?\b|\bpet cemetery\b", 3, True,
       (r"cemiterio(?:de|dos|para)?(?:pets?|animais|caes|gatos)", r"pets?cemiterio", r"petcemetery")),
    _R("B", rf"\b(?:jazigos?|nichos?|tumulos?|sepultamentos?|sepulturas?|enterros?|gavetas?|campas?)(?: (?:individual|individuais|coletivos?))?{_DE} {PET}\b", 3, True),

    # ---- C. Cemitérios
    _R("C", r"\bparques? cemiteria(?:l|is)\b|\bcemiterios? (?:parque|vertical|verticais|jardim|municipal|historico|particular)\b|\bparques? memoria(?:l|is)\b|\bmemorial parque\b|\bnecropoles?\b|\bcampos? santos?\b", 3, True,
       (r"parquecemiterial", r"parquememorial", r"memorialparque", r"cemiterioparque", r"cemiteriovertical", r"cemiteriojardim", r"necropole")),
    _R("C", r"\bcemiterios?\b|\bcemetery\b|\bcemeteries\b|\bcemiterial\b|\bcementerios?\b|\bgraveyards?\b", 3,
       compacto=(r"cemiterio", r"cemetery", r"cementerio")),
    _R("C", r"\b(?:jazigos?|ossuarios?|columbarios?|sepultamentos?|sepulturas?|gavetas? cemiteriais|lotes? de jazigo)\b", 1),

    # ---- D. Floriculturas
    _R("D", r"\b(?:coroas?|arranjos?|flores|buques?|cestas?)(?: \w+){0,3} (?:para|de|em|no|nos|ao) (?:velorios?|funera(?:l|is)|sepultamentos?|cemiterios?|despedidas?)\b|\bcoroas?(?: de)? (?:flores|funebres?|funerarias?|de homenagens?|para velorio)\b|\bflores (?:para|de|em) (?:velorios?|funera(?:l|is)|homenagens?|cemiterios?|sepultamentos?|luto|condolencias?)\b|\barranjos? (?:funebres?|funerarios?|de homenagens?|florais?|de flores)\b|\bcoroa de flor\b", 3, True,
       (r"coroas?(?:de)?flores", r"coroasfunebres", r"floresparavelorio")),
    _R("D", r"\b(?:industria|fabrica|fabricantes?|atacado|distribuidora|atacadista) de coroas\b|\bcoroas (?:para|de) (?:funerarias?|velorios?)\b", 3, True,
       (r"industriadecoroas", r"fabricadecoroas")),
    _R("D", r"\bfloriculturas?\b|\bfloristas?\b|\bflower shop\b|\bfloricultor[ae]?s?\b", 3, compacto=(r"floricultura", r"florista", r"flowershop")),
    _R("D", r"\batelie (?:floral|de flores)\b|\bdesign floral\b|\bdecorac(?:ao|oes) floral\b|\bcestas? de flores\b|\bentrega de flores\b|\bbuques?\b|\bflores naturais\b", 2, True,
       (r"ateliefloral", r"designfloral")),
    _R("D", r"\bflores\b|\bfloral\b|\borquideas?\b|\brosas\b", 1, nao_antes=ESTUDANTE,
       compacto=(r"flores(?!t)", r"floral", r"flowers")),

    # ---- E. Crematórios e funerárias pet
    _R("E", rf"\b{FUNEBRES}{_DE} {PET}\b|\b{PET} {FUNEBRES}\b|\bcremac(?:ao|oes) (?:individual|coletiva)s?{_DE} {PET}\b", 3, True,
       (r"(?:crematorio|cremacao|funeraria|funeral|memorial|urnas?|despedida|luto)(?:de|do|para)?(?:pets?|animal|animais|caes|gatos)",
        r"pets?(?:crematorio|cremacao|funeraria|funeral|memorial|urnas?|despedida|luto|descanso|eterno|angels?|heaven|forever)")),
    _R("E", r"\b(?:luto|despedida|partida|saudade) (?:pet|animal|do (?:seu|meu) pet)\b|\bpet (?:descanso|eterno|angels?|heaven|forever|saudade)\b|\bcremac(?:ao|oes) de animais\b", 2, True),
    _R("E", r"\b(?:crematorios?|cremac(?:ao|oes)|funerarias?|urnas?)\b", 2, requer=rf"\b{PET}\b"),

    # ---- F. Crematórios e funerárias humanas
    _R("F", r"\bfunerari[oa]s?\b|\bservicos? funerarios?\b|\bagencias? funerarias?\b|\bfuneral (?:home|director|services?)s?\b|\bfunerais?\b|\bfuneral\b|\bfunerales\b|\bservicios? funebres\b|\bsepelios?\b|\bvelatorios?\b|\bfunebres?\b|\buitvaart\w*", 3,
       compacto=(r"funerari[oa]", r"funeral", r"funerais", r"sepelio", r"velatorio", r"uitvaart")),
    _R("F", r"\bcrematorios?\b|\bcremac(?:ao|oes)\b|\bcrematory\b|\bcremations?\b|\bburials?\b|\bmortuar(?:y|io|ia|ios|ias)\b|\bdeath ?care\b", 3,
       compacto=(r"crematorio", r"cremacao", r"cremation", r"mortuar")),
    _R("F", r"\btanatoprax(?:ia|ista)\b|\btanatopratic[oa]\b|\bnecromaquiagem\b|\bsomatoconservac|\bembalm(?:ing|ers?)\b|\bembalsam(?:amento|amiento)\b|\bthanatoprac\w*|\bnecrop(?:sia|sias)\b", 3, nao_antes=ESTUDANTE,
       compacto=(r"tanatopraxia", r"tanato", r"thanato", r"thana", r"embalm", r"necro")),
    _R("F", r"\b(?:caixoes|caixao|ataudes?|feretros?|coffins?|caskets?|urnas? (?:funerarias?|mortuarias?|de madeira|cinerarias?|ecologicas?|biodegradaveis))\b", 3, True,
       (r"ataud", r"coffin", r"casket", r"caixao", r"caixoes")),
    _R("F", r"\burnas?\b|\burns?\b", 2, nao_antes=r"\b(?:eleitora(?:l|is)|eletronicas?)(?: \w+){0,2} $", compacto=(r"urnas",)),
    _R("F", r"\bplacas? de velorio\b|\bplaca de falecimento\b", 1, True),
    _R("F", r"\brepatriac(?:ao|oes|ion|iones)\b|\brepatriations?\b", 2, compacto=(r"repatria",)),
    _R("F", r"\bpax\b", 1, compacto=(r"pax",)),  # marca muito usada por funerárias e planos (Pax X); sozinha não confirma
    _R("F", r"\b(?:salas?|capelas?) (?:de |para )?(?:velorio|mortuarias?)\b|\bvelorios?\b|\burnas? funerarias?\b|\bremoc(?:ao|oes)\b(?= .*\b(?:corpo|obito|funer))", 2,
       compacto=(r"velorio",)),
    # "traslado" também é transporte de passageiros (aeroporto): só conta com contexto funerário no perfil
    _R("F", r"\btranslados?\b|\btraslados?\b", 2, compacto=(r"tra(?:n)?slados?",),
       requer=r"funer|obito|corpo|velori|sepult|cremac|tanato|repatria|falecid|mortuar|urna|ataud|caixao|luto"),
    _R("F", r"\bcerimon(?:ia|ias|ial|iais)(?: \w+){0,2} (?:de )?(?:despedidas?|funebres?|funerais|funerarias?)\b|\bcelebrantes? (?:de |do )?(?:funera(?:l|is)|despedidas?|ramo funerario)\b|\bagentes? funerarios?\b|\bconsultor(?:a)? funerari[oa]\b", 3, True),
    _R("F", r"\bobituarios?\b|\bfalecimentos?\b|\bnotas? de falecimento\b|\bhomenagens? postumas?\b|\bobito\b", 1),

    # ---- G. Seguro de vida e planos funerários
    _R("G", r"\bplanos? (?:funerarios?|funeral|de assistencia(?: familiar| funeral| funeraria)?|de luto|familiar(?:es)?|pax|de protecao(?: familiar)?|assistencial)\b|\bassistencia (?:familiar|funeral|funeraria|pos vida)\b", 3, True,
       (r"planos?funerarios?", r"planofuneral", r"assistenciafuneral", r"assistenciafamiliar", r"planofamiliar")),
    _R("G", r"\bseguros? de vida\b|\bseguradoras?\b|\bcorretor(?:a|es|as)? de seguros?\b|\bcorretora\b(?=.*\bseguro)|\bsusep\b|\bseguro funeral\b|\blife insurance\b|\binsurance\b", 3, True,
       (r"segurodevida", r"seguradora", r"corretoradeseguros", r"corretordeseguros")),
    _R("G", r"\bseguros\b|\bprevidencia privada\b|\bprotec(?:ao|oes) (?:familiar|financeira)\b", 2, compacto=(r"seguros",)),
    _R("G", r"\bplan(?:es)? (?:funerarios?|de prevision|de sepelio)\b|\bprevision funeraria\b|\bseguros? de sepelio\b|\bplanos? (?:pre|pos) necessidade\b|\bfuneral (?:plans?|insurance)\b", 3, True,
       (r"prevision", r"planfunerario")),
    _R("G", r"\bseguro\b|\bprevidencia\b|\bpax\b", 1, compacto=(r"pax", r"prev(?:$|[._\d])")),

    # ---- H. Clínicas e hospitais veterinários
    _R("H", r"\b(?:clinicas?|hospita(?:l|is)|centros?|consultorios?|atendimento|pronto (?:socorro|atendimento)|plantao|unidade|policlinica|especialidades?) veterinari[oa]s?\b|\bmedic[oa]s? veterinari[oa]s?\b|\bvet (?:clinic|hospital|care|center)\b|\bhospital vet\b|\bclinica vet\b|\bveterinary\b|\bclinica (?:de |para )?(?:pequenos animais|caes e gatos|animais)\b", 3, True,
       (r"clinicaveterinaria", r"hospitalveterinario", r"centroveterinario", r"clinivet", r"hospvet", r"hospitalvet",
        r"vetclinic", r"clinicavet", r"vetcare", r"vetcenter", r"centrovet", r"vethospital", r"policlinicavet")),
    _R("H", r"\bveterinari[oa]s?\b|\bmedicina veterinaria\b", 2, nao_antes=ESTUDANTE, compacto=(r"veterinari[ao]",)),
    _R("H", r"\bcrmv\b", 3),
    _R("H", r"\bvet\b|\bvets\b", 1, nao_antes=ESTUDANTE, compacto=(r"(?:^|[._\d])vet(?:s|erinari\w*)?(?:$|[._\d])", r"^vet", r"vet$")),

    # ---- I. Pet shops e serviços pet
    _R("I", rf"\bpet ?shops?\b|\bbanho (?:e|&) tosa\b|\btosa (?:higienica|na tesoura|bebe)\b|\bhote(?:l|is|lzinho)s?{_DE} {PET}\b|\b(?:pet|dog|cat) hotel\b|\bhotel (?:pet|canino|felino)\b|\bcreches? (?:canina|pet|para caes|de caes|para pets)\b|\bdog ?walker\b|\bpasseador(?:a)? de caes\b|\badestra(?:mento|dor|dora)\b|\bracoes?\b|\bagro ?pet\b|\bpet ?care\b|\bpet ?center\b|\bpet ?store\b|\bacessorios? (?:pet|para pets?|para caes|para animais)\b|\bestetica (?:animal|pet|canina|felina)\b|\bgroom(?:er|ing)\b|\bspa (?:pet|canino)\b|\bpet spa\b|\btaxi dog\b|\b(?:pet|cat|dog) ?sitter\b|\bday ?care (?:pet|canino)\b", 3, True,
       (r"petshop", r"banhoetosa", r"banhotosa", r"pethotel", r"hotelpet", r"dogwalker", r"petcare", r"petcenter",
        r"petstore", r"agropet", r"petsitter", r"catsitter", r"dogsitter", r"adestra", r"crechecanina", r"tosa(?:$|[._])")),
    _R("I", r"\btosa\b|\bbanho\b(?=.*\b(?:pet|caes|cao|gatos?|tosa)\b)|\bpet ?friendly\b", 2),
    _R("I", rf"\b{PET}\b", 1, nao_antes=ESTUDANTE, compacto=(r"pets?(?:$|[._\d])", r"^pets?")),

    # ---- J. Igrejas e comunidades religiosas
    _R("J", r"\bigrejas?\b|\bparoquias?\b|\bdioceses?\b|\barquidioceses?\b|\bcatedra(?:l|is)\b|\bcapelania\b|\bcongregac(?:ao|oes)\b|\bassembleia de deus\b|\bcomunidades? (?:catolica|evangelica|crista|religiosa|de fe|paroquial|batista|presbiteriana|metodista|adventista)s?\b|\bchurch\b|\biglesia\b|\bcentros? espiritas?\b|\bcasas? espiritas?\b|\bfederac(?:ao|oes) espirita\b|\bsinagogas?\b|\bcomunidade (?:judaica|islamica)\b|\bpastora(?:l|is)\b|\bminister(?:io|ios) (?:evangelico|apostolico|de louvor|cristao|da palavra)\b|\btemplos?\b", 3, True,
       (r"igreja", r"paroquia", r"diocese", r"catedral", r"church", r"iglesia", r"assembleiadedeus",
        r"centroespirita", r"capelania", r"comunidadecatolica", r"comunidadeevangelica")),
    _R("J", r"\bmesquitas?\b", 3, requer=r"\b(?:isl\w*|muculman\w*|allah|alcorao|ramada)\b|comunidade islamica"),  # Mesquita também é sobrenome
    # Religião declarada por uma pessoa ("Católica", "evangélico") não é igreja: exige contexto institucional.
    _R("J", r"\bespirit(?:a|as|ismo)\b|\bumbanda\b|\bcandomble\b|\bterreiro\b|\bministerio\b|\bevangelica\b|\bcatolica\b|\bbatista\b|\bpresbiteriana\b|\bmetodista\b|\badventista\b|\bluterana\b|\banglicana\b|\bpentecostal\b|\bsantuarios?\b", 2,
       requer=r"\b(?:igrejas?|paroquias?|comunidade|congregac\w*|templos?|missas?|cultos?|pastoral|diocese|capelania|ministerio \w+|celebrac\w*|fieis|peregrin\w*|romaria|terreiro|centro espirita|casa espirita)\b"),
    _R("J", r"\bpastor(?:a)?\b|\bpadre\b|\bfrei\b|\breverend[oa]\b|\bbispo\b|\bmissionari[oa]\b|\bcapela[oa]\b|\bevangelho\b|\bcultos?\b|\bmissas?\b", 1),

    # ---- K. Hospitais e cuidados paliativos
    _R("K", r"\bcuidados? paliativos?\b|\bmedicina paliativa\b|\bpaliativistas?\b|\bpaliativos?\b|\bhospices?\b|\bclinicas? oncologicas?\b|\bcentros? oncologicos?\b|\binstitutos? do cancer\b|\bhospita(?:l|is) do cancer\b|\bsanta casa\b|\bhome ?care\b|\batenc(?:ao|ao) domiciliar\b|\binternac(?:ao|oes) domiciliar\b|\bhospital dia\b", 3, True,
       (r"paliativ", r"hospice", r"santacasa", r"homecare", r"oncolog", r"hospitaldocancer")),
    _R("K", r"\bhospita(?:l|is)\b|\bhospitalar\b|\boncologi(?:a|co|ca)\b|\bonco\b|\bquimioterapia\b|\bradioterapia\b|\bhemodialise\b", 2,
       nao_antes=ESTUDANTE, compacto=(r"hospital",)),
    _R("K", r"\bdoulas? (?:de|do) fim de vida\b|\bdeath doulas?\b|\bend of life (?:doula|care)\b|\bfim de vida\b", 2, True),
    _R("K", r"\bcasas? de repouso\b|\bilpi\b|\bresidencia(?:l)? (?:senior|geriatric[oa]|para idosos)\b|\bcuidadores? de idosos\b|\bgeriatri(?:a|co|ca)\b", 1),

    # ---- L. Organizações de apoio ao luto
    _R("L", r"\bapoio (?:ao|a|aos|as) (?:luto|enlutad[oa]s)\b|\bgrupos? de (?:apoio (?:ao )?)?(?:luto|enlutad[oa]s)\b|\bacolhimento (?:ao |do |de |no )?(?:luto|enlutad[oa]s)\b|\benlutad[oa]s\b|\bluto (?:parental|materno|paterno|perinatal|gestacional|neonatal|infantil|por suicidio)\b|\bmaes? de anjos?\b|\bpais? de anjos?\b|\brede de apoio (?:ao |de |no )?luto\b|\bposvenc(?:ao|ao)\b|\bsobreviventes? (?:do|de) suicidio\b|\bperda gestacional\b|\bgrief support\b|\bpais enlutados\b", 3, True,
       (r"enlutad", r"lutoparental", r"lutomaterno", r"apoioaoluto", r"grupodeluto", r"maesdeanjo", r"acolhimentoaoluto")),
    _R("L", rf"\b{LUTO}\b", 2, requer=r"\b(?:associac(?:ao|oes)|instituto|grupos?|coletivo|ong|projeto|rede|acolhimento|fundac(?:ao)|movimento|roda de conversa|encontros?)\b"),
    _R("L", r"\bluto\b|\blutos\b|\bduelo\b|\bgrief\b", 1, compacto=(r"luto(?:$|[._\d])", r"^luto")),
    _R("L", r"\bgrief (?:group|community|network|circle)\b|\bdeath,? dying (?:e|and|&) grief\b|\bacompanamiento (?:en el|del) duelo\b|\bgrupos? de duelo\b", 3, True),

    # ---- M. Psicólogos e terapeutas do luto
    _R("M", r"\b(?:terapia|psicologia|psicoterapia|especialista|especializacao|acompanhamento|atendimento|elaborac(?:ao|ao)|processo|cuidado)s? (?:d[oe]s?|em|n[oa]|para|ao|a) (?:luto|perdas?|enlutad[oa]s)\b|\btanatolog(?:ia|o|a|ista)s?\b|\bluto e perdas?\b|\bperdas? e luto\b|\bgrief (?:therapist|counsel(?:or|ing))\b", 3, True,
       (r"terapiadoluto", r"psicologiadoluto", r"tanatolog", r"lutoeperdas")),
    _R("M", rf"\b{LUTO}\b", 3, True, requer=rf"\b{PSI}\b"),
    _R("M", r"\bcrp\b(?= ?\d)", 2),
    _R("M", rf"\b{PSI}\b", 1, nao_antes=ESTUDANTE, compacto=(r"psicolog", r"psicoterap", r"terapeuta")),
]

# Categoria profissional do Instagram (campo category_name), em inglês ou português.
# Cada padrão vale como evidência forte do campo "categoria do Instagram".
CATEGORIA_INSTAGRAM: list[tuple[str, list[tuple[str, int]]]] = [
    # Categoria combinada que quase toda funerária usa: conta como funerária; "cemitério" precisa de evidência própria.
    (r"funeral service e cemetery|servicos? funerarios? e cemiterio", [("F", 3)]),
    (r"^(?:cemetery|cemiterio)$", [("C", 3)]),
    (r"^(?!.*cemiter|.*cemetery).*(?:funeral|funerari)", [("F", 3)]),
    (r"monument|tombstone|headstone|lapide|marble|marmor|granite|granito|stone e tile|engraving|gravac", [("A", 2)]),
    (r"florist|flower|floricultura|florista|flores", [("D", 3)]),
    (r"veterinar|animal hospital|hospital veterinario", [("H", 3)]),
    (r"pet groomer|pet store|pet shop|pet supply|pet sitter|dog trainer|pet service|dog walker|animais de estimacao|pet breeder|tosador|adestrador", [("I", 3)]),
    (r"^pet$|^pets$|animal shelter|abrigo de animais", [("I", 1)]),
    (r"insurance|seguro|segurad", [("G", 3)]),
    (r"church|igreja|religious|religios|place of worship|local de culto|mosque|synagogue|temple|templo|paroquia|parish|ministry|ministerio", [("J", 3)]),
    (r"hospice|palliative|paliativ|cancer treatment|oncolog", [("K", 3)]),
    (r"^hospital$|^hospital |general hospital|hospital geral|medical center|centro medico", [("K", 2)]),
    (r"psycholog|psicolog|psychotherap|psicoterap|counselor|conselheiro|mental health|saude mental|therapist|terapeuta", [("M", 2)]),
    (r"support group|grupo de apoio", [("L", 2)]),
]
