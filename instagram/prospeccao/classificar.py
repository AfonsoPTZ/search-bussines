"""Classificação por regras: categoria(s), evidências, pontuação, confiança, tipo de perfil e situação.

Princípios:
- Uma palavra isolada e fraca ("flores", "pet", "luto") nunca confirma nada; precisa de outro sinal.
- @ de OUTRAS contas citados na bio ou nas legendas não contam como evidência ("Casado com @kamiladafuneraria").
- Perfis privados não podem ser contas comerciais no Instagram; perfis com sinais de pessoa física (casado(a), 💍,
  "papai", versículo, estudante, "Blog pessoal") sem sinal comercial forte vão no máximo para revisão.
- Só com @ e nome (sem bio/categoria lidas) a confiança máxima é "media".
- Publicações: um termo numa única publicação é indício fraco; vale mais quando se repete ou está num post fixado.
  Categoria sustentada só pelas publicações fica no máximo "media".
- Cada categoria é avaliada separadamente; um perfil só recebe uma segunda categoria se ela tiver evidência própria.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace

from prospeccao.categorias import CATEGORIA_INSTAGRAM, POR_CODIGO, REGRAS, SETOR
from prospeccao.perfis import Perfil, compactar, dominio, normalizar_texto

ALTA, MEDIA, BAIXA = 5, 3, 1

_MENCAO = re.compile(r"@[\w.]+")
_TEL = re.compile(r"(?:\(?\b\d{2}\)?\s?)?\b9?\d{4}[-.\s]?\d{4}\b|wa\.me/|whats(?:app)?|\bzap\b|📞|☎|📲")
_EMPRESA = re.compile(
    r"\b(?:ltda|eireli|cnpj|atendimento|atendemos|orcamentos?|delivery|entregas?|entregamos|encomendas?|pedidos?|"
    r"agende|agendamentos?|horarios?|seg a sex|segunda a sexta|24 ?h|24 horas|plantao|unidades?|filia(?:l|is)|desde (?:19|20)\d\d|"
    r"enderecos?|rua|av|avenida|rodovia|loja|empresa|servicos?|solicite|fale conosco|contato|whatsapp|vendas|"
    r"funcionamento|aberto|parcelamos|cartao|frete|e commerce|site|online)\b")
# Sinais comerciais que uma pessoa física raramente usa: com eles, marcas pessoais na bio não rebaixam o perfil.
_EMPRESA_FORTE = re.compile(
    r"\b(?:ltda|eireli|cnpj|atendimento 24|24 ?h|24 ?hs|24 ?hrs|24 horas|plantao|orcamentos?|unidades?|filia(?:l|is)|"
    r"desde (?:19|20)\d\d|ha (?:mais de )?\d+ anos|mais de \d+ anos|\d+ anos (?:de|no|en el|com voce|cuidando|atendendo|brindando)|"
    r"enderecos?|rua|av|avenida|rodovia|delivery|entregamos|vendas|loja|fale conosco|companhia|compania|associados?|"
    r"agende|planos?|nossos? servicos|nossa empresa|somos|oferecemos|trabalhamos com|fabricamos|we sell|our)\b")
_INSTITUICAO = re.compile(
    r"\b(?:igrejas?|paroquias?|dioceses?|associac(?:ao|oes)|instituto|ong|fundac(?:ao)|santa casa|hospita(?:l|is)|"
    r"grupos? de apoio|prefeitura|secretaria|conselho|federac(?:ao)|federacion|comunidade|congregac(?:ao)|santuario|centro espirita|"
    r"sem fins lucrativos|voluntari[oa]s?|projeto social|coletivo|movimento)\b")
_PROFISSIONAL = re.compile(
    r"\b(?:crp|crmv|crm|coren|crefito|oab|susep)\b|\bdra?\b|\bdoutor[a]?\b|\bpsicolog[oa]\b|\bpsicoterapeuta\b|\b\w*terapeuta\b|"
    r"\bpsicanalista\b|\bmedic[oa] veterinari[oa]\b|\bveterinari[oa]\b(?= .*\b(?:crmv|atendimento|consultas?)\b)|"
    r"\bcorretor\b|\bconsultor[a]?\b|\bespecialista\b|\bconsultas?\b|\bconsultorio\b|\batendimento online\b|"
    r"\bsess(?:ao|oes)\b|\bpastor[a]?\b|\bpadre\b|\bflorista\b|\btanatopraxista\b|\bfuneral director\b|\bcelebrante\b")
_PESSOAL = re.compile(
    r"\b(?:mae d[eao]s?|mamae|papai|pai d[eao]s?|esposa|esposo|marido|casad[oa]|namorad[oa]|noiv[oa]|filh[oa]s? d[eao]|"
    r"net[oa] d[eao]|avo d[eao]|amo |amo vcs|apaixonad[oa]|estudante|estudo n[ao]|estudo em|faculdade|universitari[oa]|"
    r"pos ?doutorand[oa]|doutorand[oa]|mestrand[oa]|pesquisador[a]?|cursando|tenho \d{1,2} anos|\d{1,2} anos de idade|"
    r"signo|vivendo|blessed|minha vida|meu mundo|"
    r"so love|perfil pessoal|conta pessoal|personal account|homem de fe|mulher de fe|filh[oa] de deus|deus no comando|"
    r"curto |torcedor[a]?|mom|dad|wife|husband|em formacao)\b")
_VERSICULO = re.compile(r"\b(?:salmos?|joao|mateus|marcos|lucas|romanos|filipenses|colossenses|efesios|proverbios|isaias|"
                        r"jeremias|corintios|galatas|hebreus|tiago|apocalipse|genesis|josue|deuteronomio)\s+\d{1,3}\s+\d{1,3}\b")
_CATEGORIAS_PESSOAIS = {"blog pessoal", "personal blog"}
# Criadores de conteúdo/influenciadores do tema (ex.: vídeos sobre tanatopraxia): sem sinal comercial forte, não são empresa.
_CRIADOR = re.compile(r"\b(?:criador[a]? de conteudo|criador a de conteudo|influencer|influenciador[a]?|creator|curiosidades)\b")
_CATEGORIAS_CRIADOR = {"criador a de conteudo digital", "criador de conteudo digital", "criadora de conteudo digital", "digital creator",
                       "blogueiro a", "blogueiro", "blogueira", "criador de reels"}
_HUMANO = re.compile(r"\b(?:velorios?|tanatoprax\w*|humanos?|humanas?|pessoas?|familiares|ente querido|translados?|"
                     r"capela|obitos?|funeral home)\b")

ROTULOS = {"usuario": "@", "nome": "nome", "bio": "bio", "categoria_ig": "categoria do Instagram", "link": "site",
           "post": "publicação", "post_fixado": "publicação fixada", "local": "local das publicações",
           "destaque": "destaque dos Stories"}
_GRUPO = {"usuario": "identidade", "nome": "identidade", "link": "identidade", "bio": "bio", "categoria_ig": "categoria_ig",
          "post": "conteudo", "post_fixado": "conteudo", "local": "conteudo", "destaque": "conteudo"}


@dataclass
class _Achado:
    regra: int
    categoria: str
    peso: int
    campo: str
    trecho: str
    oferta: bool = False  # publicações: o post que citou o termo também oferece serviço (orçamento, WhatsApp, valores...)


# Sinal de oferta de serviço numa publicação: sem isso, uma página que só FALA do tema (lendas de cemitério,
# reflexões sobre luto) não vira empresa do segmento.
_OFERTA = re.compile(
    r"\b(?:orcamentos?|whatsapp|whats|zap|atendimento|atendemos|agende|agendamentos?|contrate|contratar|encomend\w*|"
    r"faca seu pedido|pedidos (?:pelo|no|via)|entregamos|entregas? (?:para|em|gratis|24)|delivery|valores?|precos?|r \d+|\d+ reais|"
    r"parcel\w*|promoc\w*|descontos?|planos? (?:funerari\w*|de assistencia|familiar\w*|a partir|mensa\w*|por r)|"
    r"fale conosco|chame no|ligue|telefone|24 ?h|24 horas|plantao 24|nossos? servicos|oferecemos|vendas?|compre|loja|"
    r"catalogo|cotiz\w*|consulte|reserve|solicite|associe se|adesao|servicios|contactanos|presupuesto)\b")


def _sobrepoe(a, b) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _aplicar(texto: str, campo: str, completo: str | None, modo: str, achados: list):
    """modo 'texto' usa Regra.padrao; modo 'compacto' usa Regra.compacto. Compostos reservam o trecho casado.
    completo=None ignora as exigências de contexto (usado na triagem, onde qualquer indício vale)."""
    if not texto:
        return
    reservados: list[tuple[int, int]] = []
    for composto in (True, False):
        for i, r in enumerate(REGRAS):
            if r.composto != composto:
                continue
            if r.requer and completo is not None and not re.search(r.requer, completo):
                continue
            padroes = [r.padrao] if modo == "texto" else list(r.compacto)
            for p in padroes:
                for m in re.finditer(p, texto):
                    span = m.span()
                    if not composto and any(_sobrepoe(span, s) for s in reservados):
                        continue
                    if r.nao_antes and re.search(r.nao_antes, texto[max(0, span[0] - 40):span[0]]):
                        continue
                    if composto:
                        reservados.append(span)
                    if not any(a.regra == i and a.campo == campo for a in achados):
                        achados.append(_Achado(i, r.categoria, r.peso, campo, m.group(0).strip()))
                    if not composto:
                        break  # uma ocorrência por padrão e campo basta; compostos reservam todas


def _identidade(usuario: str, nome: str, completo: str, achados: list):
    usuario_txt = normalizar_texto(usuario.replace(".", " ").replace("_", " "))
    _aplicar(usuario_txt, "usuario", completo, "texto", achados)
    _aplicar(usuario.lower(), "usuario", completo, "compacto", achados)
    _aplicar(normalizar_texto(nome), "nome", completo, "texto", achados)
    _aplicar(compactar(nome), "nome", completo, "compacto", achados)


def indicios_segmento(usuario: str, nome: str) -> list[str]:
    """Termos de algum segmento (inclusive fracos) no @ ou no nome. Usado pela triagem."""
    achados: list[_Achado] = []
    _identidade(usuario, nome or "", None, achados)
    vistos = []
    for a in sorted(achados, key=lambda a: -a.peso):
        t = f"{a.categoria}:{a.trecho}"
        if t not in vistos:
            vistos.append(t)
    return vistos


def _sinais_pessoais(p: Perfil, bio: str, cat_ig: str) -> str:
    m = _PESSOAL.search(bio)
    if m:
        return m.group(0).strip()
    m = _VERSICULO.search(bio)
    if m:
        return f"versículo '{m.group(0)}'"
    for emoji, rot in (("💍", "💍 (aliança)"), ("🎂", "🎂 (aniversário)")):
        if emoji in (p.bio or ""):
            return rot
    if cat_ig in _CATEGORIAS_PESSOAIS:
        return f"categoria '{p.categoria_ig}'"
    m = _CRIADOR.search(bio)
    if m or cat_ig in _CATEGORIAS_CRIADOR:
        return f"criador de conteúdo ('{m.group(0) if m else p.categoria_ig}')"
    return ""


def _tipo(p: Perfil, bio: str, nome: str, cat_ig: str) -> tuple[str, list[str]]:
    sinais = []
    if p.privado:
        sinais.append("perfil privado (contas comerciais não podem ser privadas)")
        return "pessoal", sinais
    if p.conta_comercial:
        sinais.append("conta comercial/profissional")
    if p.categoria_ig:
        sinais.append(f"categoria do Instagram: {p.categoria_ig}")
    if p.link_externo:
        sinais.append("tem link externo")
    texto = f"{nome} {bio}"
    tel = bool(_TEL.search(_MENCAO.sub(" ", p.bio or "")))
    if tel:
        sinais.append("telefone/WhatsApp na bio")
    m = _EMPRESA.search(texto)
    if m:
        sinais.append(f"termo comercial: '{m.group(0)}'")
    forte = _EMPRESA_FORTE.search(texto)
    pessoal = _sinais_pessoais(p, bio, cat_ig)
    if pessoal and not forte and not tel:
        sinais.append(f"sinal de pessoa física: {pessoal}")
        return "pessoal", sinais
    inst = _INSTITUICAO.search(texto)
    if inst:
        sinais.append(f"termo institucional: '{inst.group(0)}'")
        return "instituicao", sinais
    prof = _PROFISSIONAL.search(texto)
    if prof:
        sinais.append(f"termo profissional: '{prof.group(0)}'")
        return "profissional", sinais
    if sum(1 for s in sinais if not s.startswith("perfil")):
        return "empresa", sinais
    if pessoal:
        sinais.append(f"sinal de pessoa física: {pessoal}")
        return "pessoal", sinais
    return "indeterminado", sinais


def _nivel(pontos: float) -> str:
    return "alta" if pontos >= ALTA else "media" if pontos >= MEDIA else "baixa"


def _tokens_relevantes(t: str) -> set[str]:
    return {x for x in normalizar_texto(t).split() if len(x) >= 4}


def _conteudo(p: Perfil, completo: str, achados: list) -> list[str]:
    """Publicações, locais e destaques. Devolve as fontes usadas (para registrar no resultado)."""
    fontes = []
    nome_tokens = _tokens_relevantes(f"{p.nome} {p.usuario.replace('.', ' ').replace('_', ' ')}")
    por_regra: dict[int, list[_Achado]] = defaultdict(list)
    for post in p.posts or []:
        campo = "post_fixado" if post.get("fixado") else "post"
        tmp: list[_Achado] = []
        texto = normalizar_texto(_MENCAO.sub(" ", post.get("texto") or ""))
        _aplicar(texto, campo, completo, "texto", tmp)
        for h in post.get("hashtags") or []:
            _aplicar(h.lower(), campo, completo, "compacto", tmp)
        sem_nome = " ".join(w for w in texto.split() if w not in nome_tokens)  # "plantão" de "Assustados de Plantão" não é oferta
        oferta = bool(_OFERTA.search(sem_nome) or _TEL.search(post.get("texto") or ""))
        for a in {a.regra: a for a in tmp}.values():  # cada regra conta uma vez por publicação
            a.oferta = oferta
            por_regra[a.regra].append(a)
    for regra, lst in por_regra.items():
        n = len(lst)
        fixado = any(a.campo == "post_fixado" for a in lst)
        base = max(lst, key=lambda a: a.peso)
        peso = base.peso if (n >= 2 or fixado) else min(base.peso, 1)  # uma publicação isolada é só indício
        achados.append(_Achado(regra, base.categoria, peso, "post_fixado" if fixado else "post",
                               f"{base.trecho} ({n} publicaç{'ões' if n > 1 else 'ão'}{', fixada' if fixado else ''})",
                               oferta=any(a.oferta for a in lst)))
    if p.posts:
        fontes.append(f"{len(p.posts)} publicações ({sum(1 for x in p.posts if x.get('fixado'))} fixadas)")

    locais = Counter(x["local"] for x in p.posts or [] if x.get("local"))
    for local, n in locais.items():
        tmp = []
        _aplicar(normalizar_texto(local), "local", completo, "texto", tmp)
        proprio = bool(nome_tokens & _tokens_relevantes(local))  # local com o nome do próprio perfil
        for a in tmp:
            a.oferta = proprio  # local com o nome do próprio perfil = endereço do negócio
            if not (n >= 2 or proprio):
                a.peso = min(a.peso, 1)  # local visitado uma vez (ex.: um velório) não diz o que o perfil faz
            a.trecho = f"{a.trecho} ('{local}')"
            achados.append(a)
    if locais:
        fontes.append(f"{len(locais)} locais marcados")

    for titulo in p.destaques or []:
        tmp = []
        _aplicar(normalizar_texto(titulo), "destaque", completo, "texto", tmp)
        for a in tmp:
            a.oferta = True  # destaques são o "cardápio" que o próprio perfil escolheu mostrar
        achados += tmp
    if p.destaques:
        fontes.append(f"{len(p.destaques)} destaques")
    return fontes


def classificar(p: Perfil) -> dict:
    bio_original = p.bio or ""
    mencoes = sorted(set(_MENCAO.findall(bio_original)))
    nome = normalizar_texto(p.nome)
    usuario_txt = normalizar_texto(p.usuario.replace(".", " ").replace("_", " "))
    bio = normalizar_texto(_MENCAO.sub(" ", bio_original))
    cat_ig = normalizar_texto(p.categoria_ig)
    dom = dominio(p.link_externo)
    textos_posts = " ".join(normalizar_texto(_MENCAO.sub(" ", x.get("texto") or "")) for x in p.posts or [])
    completo = " ".join(x for x in (usuario_txt, nome, bio, cat_ig, normalizar_texto(dom), textos_posts,
                                    normalizar_texto(" ".join(p.destaques or []))) if x)

    achados: list[_Achado] = []
    _identidade(p.usuario, p.nome or "", completo, achados)
    _aplicar(bio, "bio", completo, "texto", achados)
    _aplicar(dom.split(".")[0] if dom else "", "link", completo, "compacto", achados)
    if cat_ig:
        for idx, (padrao, alvos) in enumerate(CATEGORIA_INSTAGRAM):
            if re.search(padrao, cat_ig):
                for cod, peso in alvos:
                    achados.append(_Achado(-1 - idx, cod, peso, "categoria_ig", p.categoria_ig))
    fontes = ["@ e nome"]
    if p.detalhes == "perfil":
        fontes.append("bio, categoria e tipo de conta")
    fontes += _conteudo(p, completo, achados)

    tipo, sinais = _tipo(p, bio, nome, cat_ig)
    if mencoes:
        sinais.append("menciona (não usado como evidência): " + ", ".join(mencoes[:5]))
    setor = bool(re.search(SETOR, completo))
    if setor:
        sinais.append("atua para o setor (fornecedor, sistema, curso, mídia ou evento)")
    so_nome = p.detalhes != "perfil"
    if p.privado:
        estado = "privado"
    elif p.detalhes == "perfil":
        estado = "completa"
    elif p.detalhes == "indisponivel":
        estado = "detalhes_indisponiveis"
    else:
        estado = "so_nome"

    por_cat: dict[str, list[_Achado]] = {}
    for a in achados:
        por_cat.setdefault(a.categoria, []).append(a)

    categorias = []
    for cod, lista in por_cat.items():
        melhor: dict[int, _Achado] = {}
        for a in lista:
            if a.regra not in melhor or a.peso > melhor[a.regra].peso:
                melhor[a.regra] = a
        pontos = float(sum(a.peso for a in melhor.values()))
        maior = max(a.peso for a in melhor.values())
        grupos = {_GRUPO[a.campo] for a in lista if a.peso >= 2 or maior == 1}  # campos com evidência própria
        pontos += min(len(grupos) - 1, 2)  # mesma atividade confirmada em campos diferentes
        if tipo in ("empresa", "instituicao", "profissional"):
            pontos += 1
        if maior == 1 and tipo not in ("empresa", "instituicao", "profissional"):
            continue  # só indício fraco num perfil sem sinal comercial: ruído
        nivel = _nivel(pontos)
        motivo_teto = ""
        if maior == 1:
            nivel, motivo_teto = "baixa", "só indícios fracos"
        if cod == "M" and not any(re.search(r"luto|perd|enlutad|tanatolog|grief|duelo", a.trecho) for a in melhor.values()):
            nivel, motivo_teto = "baixa", "profissional de psicologia/terapia sem menção a luto"
        if tipo == "pessoal" and nivel != "baixa":
            nivel, motivo_teto = "baixa", "parece perfil pessoal (pessoa física)"
        if so_nome and nivel == "alta":
            nivel, motivo_teto = "media", "bio e categoria não lidas"
        if grupos == {"conteudo"} and nivel != "baixa":
            if any(a.oferta for a in melhor.values()):
                nivel, motivo_teto = "media", motivo_teto or "evidência só nas publicações"
            else:
                nivel, motivo_teto = "baixa", "as publicações falam do tema, mas não oferecem o serviço"
        if setor and cod in ("F", "C", "A", "D", "E", "G") and nivel != "baixa":
            nivel = "media" if nivel == "alta" else nivel
            motivo_teto = motivo_teto or "atua para o setor funerário (fornecedor, sistema, curso ou mídia); confira se presta o serviço"
        evid = []
        for a in sorted(melhor.values(), key=lambda a: -a.peso):
            e = f"{ROTULOS[a.campo]}: '{a.trecho}'"
            if e not in evid:
                evid.append(e)
        categorias.append({
            "codigo": cod, "nome": POR_CODIGO[cod].nome, "pontuacao": pontos, "confianca": nivel,
            "evidencias": evid, **({"limitacao": motivo_teto} if motivo_teto else {}),
        })
    categorias.sort(key=lambda c: (-c["pontuacao"], c["codigo"]))
    categorias = _ajustar_contexto(categorias, completo)

    if any(c["confianca"] in ("alta", "media") for c in categorias):
        situacao = "identificado"
    elif categorias:
        situacao = "revisar"
    else:
        situacao = "sem_correspondencia"
    return {
        "usuario": p.usuario, "nome": p.nome, "link": p.link, "categorias": categorias, "tipo_perfil": tipo,
        "situacao": situacao, "estado_analise": estado, "sinais": sinais, "fontes": fontes,
        "etapas": list(p.etapas or []),
    }


def _ajustar_contexto(categorias: list[dict], completo: str) -> list[dict]:
    fortes = {c["codigo"] for c in categorias if c["confianca"] in ("alta", "media")}
    saida = []
    for c in categorias:
        c = dict(c)
        # Funerária/crematório/cemitério PET: termos funerários genéricos (ou a categoria "Serviços funerários e
        # cemitério") não fazem dele também um serviço para pessoas, salvo sinal humano explícito.
        explicito = any(not e.startswith("categoria do Instagram") and re.search(r"funer|velori|tanato|cerimon|cemiter|necropol", e)
                        for e in c["evidencias"])
        if c["codigo"] in ("F", "C") and fortes & {"E", "B"} and not explicito and not _HUMANO.search(completo):
            continue  # termos funerários genéricos num perfil pet: não é serviço para pessoas
        # Indício fraco numa categoria secundária de um perfil já identificado é ruído (ex.: funerária que cita "jazigos").
        if c.get("limitacao") == "só indícios fracos" and fortes - {c["codigo"]}:
            continue
        saida.append(c)
    return saida


MOTIVOS_PUBLICACOES = {  # ordem de prioridade na etapa de publicações
    "duvidoso": (0, "classificação duvidosa"),
    "conta_comercial": (1, "conta comercial sem categoria identificada"),
    "sinais_comerciais": (2, "sinais comerciais sem categoria identificada"),
    "bio_vazia": (3, "bio vazia ou curta demais"),
}


def precisa_publicacoes(perfil: dict, classificacao: dict, cfg: dict | None = None) -> tuple[int, str] | None:
    """(ordem, motivo) para ler as publicações do perfil, ou None (já classificado com clareza, privado, pessoal...).

    cfg = triagem.carregar_config()["publicacoes"]: quais motivos valem e até que prioridade de triagem a "bio vazia" vale."""
    cfg = cfg or {"motivos": list(MOTIVOS_PUBLICACOES), "bio_vazia_ate_prioridade": 1}
    if perfil.get("privado") or "publicacoes" in (perfil.get("etapas") or []) or perfil.get("detalhes") != "perfil":
        return None
    if classificacao["situacao"] == "identificado":
        return None
    motivo = None
    if classificacao["situacao"] == "revisar":
        motivo = "duvidoso"
    elif classificacao["tipo_perfil"] != "pessoal":
        cat = normalizar_texto(perfil.get("categoria_ig"))
        if perfil.get("conta_comercial") or (cat and cat not in _CATEGORIAS_PESSOAIS):
            motivo = "conta_comercial"
        elif classificacao["tipo_perfil"] in ("empresa", "instituicao", "profissional"):
            motivo = "sinais_comerciais"
        elif len(normalizar_texto(_MENCAO.sub(" ", perfil.get("bio") or ""))) < 15 and \
                (perfil.get("triagem") or {}).get("prioridade", 9) <= cfg.get("bio_vazia_ate_prioridade", 1):
            motivo = "bio_vazia"
    if not motivo or motivo not in cfg.get("motivos", MOTIVOS_PUBLICACOES):
        return None
    return MOTIVOS_PUBLICACOES[motivo]


def vale_ler_detalhes(p: Perfil) -> bool:
    """Compatibilidade: a triagem padrão (modo candidatos) leria o perfil?"""
    from prospeccao import triagem
    return triagem.deve_ler(triagem.avaliar(replace(p, privado=False))[0], "candidatos")


def segmentos_de_texto(nome: str, textos: list[str], handle: str = "") -> list[str]:
    """Segmentos A–M sugeridos por um texto solto (nome e/ou atividade de uma empresa, por exemplo).

    É a MESMA classificação usada nos perfis, só que sem perfil: por isso o resultado é sempre apenas um
    indício ("inferido"), nunca um segmento confirmado. Quem chama precisa marcá-lo como tal.
    Fonte única usada pela plataforma e pela pesquisa de empresas — não duplique esta montagem.
    """
    usuario = handle or (re.sub(r"[^a-z0-9]+", "", normalizar_texto(nome))[:30] or "empresa")
    p = Perfil(usuario=usuario, nome=nome or "", bio=" · ".join(t for t in textos if t), detalhes="perfil",
               conta_comercial=True, etapas=["lista", "perfil"])
    return [c["codigo"] for c in classificar(p)["categorias"] if c["confianca"] in ("alta", "media")]


def filtrar(resultado: dict, codigos: list[str]) -> dict:
    """Mantém só as categorias selecionadas na execução e recalcula a situação."""
    cats = [c for c in resultado["categorias"] if c["codigo"] in codigos]
    r = dict(resultado, categorias=cats)
    if any(c["confianca"] in ("alta", "media") for c in cats):
        r["situacao"] = "identificado"
    elif cats:
        r["situacao"] = "revisar"
    else:
        r["situacao"] = "sem_correspondencia"
    return r
