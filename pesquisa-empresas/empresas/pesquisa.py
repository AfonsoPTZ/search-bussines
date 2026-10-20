"""Pesquisa de uma empresa: identifica, encontra site/perfis, extrai contatos e valida o CNPJ.

Cada valor gravado guarda a URL que o comprova e a origem:
    entrada   - informado na lista
    cadastro  - base pública da Receita Federal (via API)
    site      - página do site oficial
    instagram - perfil público ou trecho do perfil exibido pelo buscador
    busca     - trecho de resultado de busca (mais fraco)
    cep       - consulta pública de CEP (completa rua/bairro/cidade a partir do CEP encontrado)
    gerado    - montado pela ferramenta (ex.: link do Google Maps, categoria inferida)
    revisao   - correção registrada depois (pelo Claude ou manualmente), com fonte

Cada valor também diz se está confirmado. Valores não confirmados (CNPJ só "provável", perfil achado só
por nome na busca, site que não pôde ser lido...) são mantidos e marcados, em vez de descartados.
"""

import html
import re
import traceback
from datetime import datetime
from urllib.parse import quote, urlparse

from rapidfuzz import fuzz

from empresas import cadastro, categorias, config, web
from empresas import cnpj as cnpjlib
from empresas.entradas import Entrada
from empresas.extrair import Achados, classificar_link, de_html, de_texto, endereco_jsonld, seguidores_em
from empresas.util import (compacto, contido_com_extras, dominio, normalizar, rotulo_dominio, sigla_uf,
                           similaridade, tokens_nome, unicos)

CAMPOS = [
    "nome_comercial", "categoria", "razao_social", "cnpj", "situacao_cadastral", "data_situacao",
    "atividade_principal", "natureza_juridica", "porte", "matriz_filial", "endereco", "bairro", "cidade", "uf",
    "cep", "google_maps", "telefones", "whatsapp", "emails", "site", "instagram", "seguidores_instagram",
    "facebook", "linkedin", "outros_canais", "horario_funcionamento", "avaliacao",
    "telefone_cadastro", "email_cadastro",
]
CAMPOS_MULTIPLOS = {"telefones", "whatsapp", "emails", "outros_canais", "telefone_cadastro", "email_cadastro"}
CAMPOS_ESSENCIAIS = ["cnpj", "razao_social", "endereco", "cep", "telefones", "whatsapp", "emails", "site", "instagram"]

_PRIORIDADE = {"revisao": 0, "entrada": 1, "site": 2, "cadastro": 3, "instagram": 4, "cep": 5, "busca": 6, "gerado": 7}
_PRIORIDADE_CADASTRO_PRIMEIRO = {"revisao": 0, "entrada": 1, "cadastro": 2, "site": 3, "instagram": 4, "cep": 5,
                                 "busca": 6, "gerado": 7}
_CAMPOS_CADASTRAIS = {"razao_social", "endereco", "bairro", "cidade", "uf", "cep", "situacao_cadastral"}

# Domínios que nunca são o "site oficial" de uma empresa (redes, buscadores, agregadores de CNPJ, marketplaces).
NAO_OFICIAIS = {
    "instagram.com", "facebook.com", "linkedin.com", "youtube.com", "tiktok.com", "twitter.com", "x.com",
    "threads.net", "pinterest.com", "linktr.ee", "wa.me", "whatsapp.com", "google.com", "google.com.br",
    "goo.gl", "bing.com", "yahoo.com", "wikipedia.org", "gov.br", "jusbrasil.com.br", "reclameaqui.com.br",
    "cnpj.biz", "casadosdados.com.br", "econodata.com.br", "maiscnpj.com.br", "cnpja.com", "cnpj.ws",
    "consultasocio.com", "empresaqui.com.br", "cnpj.info", "solutudo.com.br", "guiamais.com.br",
    "apontador.com.br", "telelistas.net", "yelp.com", "tripadvisor.com.br", "tripadvisor.com", "ifood.com.br",
    "mercadolivre.com.br", "olx.com.br", "glassdoor.com.br", "indeed.com", "infojobs.com.br", "efirma.com.br",
    "informecadastral.com.br", "cnpjconsultas.com", "listamais.com.br", "encontra.com", "brasilapi.com.br",
    "receitaws.com.br", "opencnpj.org", "minhareceita.org", "empresasdobrasil.com", "consultacnpj.com",
    "cadastroempresa.com.br", "serasaexperian.com.br", "dnb.com", "b2bleads.com.br", "speedio.com.br",
    "tudosobretodos.info", "advdinamico.com.br", "situacao-cadastral.com", "kekanto.com.br", "foursquare.com",
    "waze.com", "uber.com", "rappi.com.br", "aiqfome.com", "booking.com", "airbnb.com.br", "doctoralia.com.br",
    "amazon.com.br", "shopee.com.br", "magazineluiza.com.br", "americanas.com.br", "cylex.com.br",
    "hotfrog.com.br", "brasil.cylex.com.br", "acheaqui.com.br", "guiafacil.com", "procuroacho.com",
    "linkedin.cn", "bloomberg.com", "zoominfo.com", "crunchbase.com", "rocketreach.co", "emis.com",
    "todosnegocios.com", "brasillocais.com", "lojas24.com", "guiapj.com.br", "monitorcnpj.com.br",
    "situacaocadastral.info", "datastone.com.br", "acheiempresa.com.br", "cnpj.in", "benditoguia.com.br",
    "guiafacil.com", "empresascnpj.com", "cnpjbrasil.com", "consultaempresa.com.br", "telelistas.com.br",
}

_RE_SITE_EM_TEXTO = re.compile(r"\b(?:https?://)?((?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com\.br|net\.br|org\.br|ind\.br|art\.br|com|net|org|br|store|shop|site|online))\b", re.I)
_RE_PAGINA_UTIL = re.compile(
    r"contat|contact|fale|atendimento|sobre|quem.?somos|institucional|a-empresa|nossa-empresa|/empresa/?$|privacidade|privacy|"
    r"termos|politica|pol%C3%ADtica|lojas|unidades|onde.?estamos|localiza|endereco|endere%C3%A7o",
    re.I,
)


def oficial_possivel(url: str) -> bool:
    d = dominio(url)
    return bool(d) and not any(d == n or d.endswith("." + n) for n in NAO_OFICIAIS)


class Registro:
    def __init__(self, e: Entrada):
        self.d = {
            "linha": e.linha,
            "entrada": e.original,
            "tipo_entrada": e.tipo,
            "pistas": {"nome": e.nome, "cidade": e.cidade, "uf": e.uf, "outras": e.dicas},
            "status": "",
            "confianca": "",
            "pontuacao_cnpj": None,
            "data_pesquisa": datetime.now().isoformat(timespec="seconds"),
            "campos": {},
            "candidatos_cnpj": [],
            "alternativas": [],
            "divergencias": [],
            "observacoes": [],
            "consultas": [],
            "nao_encontrados": [],
            "nao_confirmados": [],
        }
        self.textos = []  # títulos/trechos vistos (para inferir a categoria); não vai para o registro

    @classmethod
    def de_dict(cls, d: dict) -> "Registro":
        r = cls.__new__(cls)
        r.d = d
        r.d.setdefault("alternativas", [])
        r.textos = []
        return r

    # --- campos ---------------------------------------------------------------------------------------
    def add(self, campo: str, valor, fonte: str, origem: str, confirmado: bool = True):
        if valor is None:
            return
        valor = str(valor).strip()
        if not valor:
            return
        lista = self.d["campos"].setdefault(campo, [])
        chave = normalizar(valor) if campo not in ("site", "instagram", "facebook", "linkedin") else valor.lower().rstrip("/")
        for item in lista:
            igual = (normalizar(item["valor"]) if campo not in ("site", "instagram", "facebook", "linkedin")
                     else item["valor"].lower().rstrip("/")) == chave
            if igual and item["fonte"] == fonte:
                item["confirmado"] = item.get("confirmado", True) or confirmado
                return
        lista.append({"valor": valor, "fonte": fonte, "origem": origem, "confirmado": confirmado})

    def entradas(self, campo: str, so_confirmado: bool = False) -> list[dict]:
        """Valores do campo: confirmados primeiro, depois pela prioridade da origem."""
        prior = _PRIORIDADE_CADASTRO_PRIMEIRO if campo in _CAMPOS_CADASTRAIS else _PRIORIDADE
        itens = [i for i in self.d["campos"].get(campo, []) if i.get("confirmado", True) or not so_confirmado]
        return sorted(itens, key=lambda x: (not x.get("confirmado", True), prior.get(x["origem"], 9)))

    def valor(self, campo: str, so_confirmado: bool = False) -> str:
        e = self.entradas(campo, so_confirmado)
        return e[0]["valor"] if e else ""

    def valores(self, campo: str, so_confirmado: bool = False) -> list[str]:
        vistos, saida = set(), []
        for item in self.entradas(campo, so_confirmado):
            k = normalizar(item["valor"]) or item["valor"]
            if k not in vistos:
                vistos.add(k)
                saida.append(item["valor"])
        return saida

    def confirmado(self, campo: str) -> bool:
        """O valor principal do campo está confirmado? (False também quando o campo está vazio)"""
        e = self.entradas(campo)
        return bool(e) and e[0].get("confirmado", True)

    def alternativa(self, tipo: str, valor: str, motivo: str, fonte: str = ""):
        """Guarda algo encontrado mas rejeitado por evidência contrária (não entra nas colunas principais)."""
        self.d["alternativas"].append({"tipo": tipo, "valor": valor, "motivo": motivo, "fonte": fonte})

    def obs(self, texto: str):
        if texto not in self.d["observacoes"]:
            self.d["observacoes"].append(texto)

    def divergencia(self, texto: str):
        if texto not in self.d["divergencias"]:
            self.d["divergencias"].append(texto)

    def consulta(self, texto: str):
        self.d["consultas"].append(texto)


# ------------------------------------------------------------------------------------------- Instagram

def perfil_instagram(handle: str) -> dict:
    """Nome exibido e resumo público do perfil (o que o Instagram mostra sem login)."""
    url = f"https://www.instagram.com/{handle}/"
    pag = web.baixar(url)
    if pag.status != 200 or not pag.html:
        return {"url": url, "nome": "", "resumo": "", "erro": pag.erro or f"HTTP {pag.status}"}
    _, meta = de_html(pag.html, url)
    titulo = meta.get("titulo", "")
    nome = titulo.split(" (@")[0].strip() if " (@" in titulo else ""
    if nome.lower() == "instagram":
        nome = ""
    return {"url": url, "nome": nome, "resumo": meta.get("descricao", ""), "erro": ""}


def _trechos_instagram(r: Registro, handle: str, confirmado: bool = True) -> tuple[Achados, list[str]]:
    """Busca o perfil no buscador: o trecho exibido costuma conter a bio (telefone, site, endereço) e o
    contador de seguidores. `confirmado` diz se o próprio perfil é confirmado como sendo da empresa."""
    achados, sites = Achados(), []
    consulta = f'"{handle}" instagram'
    r.consulta(f"busca: {consulta}")
    url_perfil = f"https://www.instagram.com/{handle}/"
    seguidores = []
    for x in web.buscar(consulta, 10):
        partes = urlparse(x.url).path.strip("/").split("/") if "instagram.com" in x.url else [""]
        if partes[0].lower() != handle:
            continue
        texto = f"{x.titulo}\n{x.trecho}"
        r.textos.append(texto)
        a = de_texto(texto)
        a.instagram = []
        for f in a.telefones:
            r.add("telefones", f, url_perfil, "instagram", confirmado)
        for f in a.whatsapp:
            r.add("whatsapp", f, url_perfil, "instagram", confirmado)
        for e in a.emails:
            r.add("emails", e, url_perfil, "instagram", confirmado)
        for h in a.horarios[:1]:
            r.add("horario_funcionamento", h, url_perfil, "instagram", confirmado)
        # Contador de seguidores: prefere o resultado da página principal do perfil (não /reels, /p/...).
        if (n := seguidores_em(texto)) is not None:
            seguidores.append((len(partes) > 1, n))
        achados.juntar(a)
        for m in _RE_SITE_EM_TEXTO.finditer(texto):
            if oficial_possivel(m.group(1)) and "instagram" not in m.group(1).lower():
                sites.append(dominio(m.group(1)))
        if not r.valor("nome_comercial") and " (@" in x.titulo:
            r.add("nome_comercial", x.titulo.split(" (@")[0].strip(), url_perfil, "instagram", confirmado)
    if seguidores and not r.valor("seguidores_instagram"):
        r.add("seguidores_instagram", str(sorted(seguidores)[0][1]), url_perfil, "instagram", confirmado)
    return achados, unicos(sites)


# ----------------------------------------------------------------------------------------- site oficial

# Palavras de segmento: não identificam uma empresa ("cemiterio.net.br" não é o site do "Cemitério Parque Iguaçu").
_PALAVRAS_DE_SEGMENTO = {
    "cemiterio", "cemiterios", "crematorio", "funeraria", "funerarias", "funerario", "funeral", "plano", "planos",
    "floricultura", "flores", "padaria", "panificadora", "confeitaria", "restaurante", "pizzaria", "lanchonete",
    "sorveteria", "cafeteria", "bar", "farmacia", "drogaria", "clinica", "consultorio", "odontologia", "academia",
    "escola", "colegio", "supermercado", "mercado", "auto", "pet", "shop", "petshop", "salao", "barbearia",
    "imobiliaria", "hotel", "pousada", "livraria", "otica", "oficina", "distribuidora", "casa", "centro", "studio",
    "estudio", "parque", "jardim", "memorial", "igreja", "hospital", "seguros", "seguradora", "advocacia",
    "contabilidade", "construtora", "materiais", "moveis", "moda", "store", "online", "brasil", "oficial",
}


def _termos_distintivos(nome: str) -> list[str]:
    return [t for t in tokens_nome(nome) if t not in _PALAVRAS_DE_SEGMENTO and len(t) >= 3]


def _pontuar_dominio(nome: str, url: str) -> float:
    rot, comp = rotulo_dominio(url), compacto(nome)
    if len(rot) < 3 or not comp:
        return 0.0
    s = fuzz.ratio(comp, rot)
    if min(len(rot), len(comp)) >= 5 and (rot in comp or comp in rot):
        s = max(s, 88.0)
    # O domínio precisa trazer algo distintivo do nome, não só a palavra do segmento.
    distintivos = _termos_distintivos(nome)
    if distintivos and not any(t in rot for t in distintivos):
        s = min(s, 60.0)
    return s


def _pontuar_site(nome: str, url: str, titulo: str) -> float:
    """Domínio parecido com o nome vale sempre; título só vale em página inicial (diretórios e guias
    de empresas usam o nome da empresa no título, mas em caminhos longos como /empresa/nome-123)."""
    s = _pontuar_dominio(nome, url)
    if len([p for p in urlparse(url).path.split("/") if p]) <= 1:
        s = max(s, similaridade(nome, titulo.split("|")[0].split(" - ")[0]) * 0.95)
    return s


def descobrir_site(r: Registro, nome: str, cidade: str, uf: str, sugeridos: list[str]) -> str:
    consulta = " ".join(x for x in (nome, cidade, uf) if x)
    r.consulta(f"busca: {consulta}")
    resultados = web.buscar(consulta, 12)
    melhor, melhor_pts = "", 0.0
    for x in resultados:
        url = x.url
        if not url.startswith("http"):
            continue
        if not oficial_possivel(url):
            # Perfis de redes sociais com o mesmo nome: entram como NÃO confirmados (só o nome bate; podem ser
            # de homônimos). Viram confirmados se o site oficial linkar o mesmo perfil.
            a = Achados()
            classificar_link(url, a)
            if similaridade(nome, x.titulo) >= 85:
                for campo, lista in (("instagram", a.instagram), ("facebook", a.facebook), ("linkedin", a.linkedin)):
                    for v in lista:
                        r.add(campo, v, url, "busca", confirmado=False)
            continue
        pts = _pontuar_site(nome, url, x.titulo)
        if dominio(url) in sugeridos:
            pts += 20
        if pts > melhor_pts:
            # Usa o domínio principal (agencia.petrobras.com.br -> petrobras.com.br).
            melhor, melhor_pts = f"https://{dominio(url)}/", pts
    if not melhor and sugeridos:
        return f"https://{sugeridos[0]}/", 85.0
    return (melhor, melhor_pts) if melhor_pts >= 80 else ("", 0.0)


def ler_site(r: Registro, site: str) -> tuple[list[tuple[str, Achados, dict]], str]:
    """Lê a página inicial e até MAX_PAGINAS_SITE-1 páginas de contato/sobre/privacidade.

    Retorna (páginas, motivo da falha). Sites com proteção anti-robô (ex.: Cloudflare) não são contornados.
    """
    paginas = []
    p_url = urlparse(site)
    host = p_url.netloc
    sem_www = host.removeprefix("www.")
    caminho = p_url.path or "/"
    tentativas = unicos([site, f"https://www.{sem_www}{caminho}", f"https://{sem_www}{caminho}", f"http://www.{sem_www}{caminho}"])
    inicial, motivo = None, ""
    for t in tentativas:
        p = web.baixar(t)
        r.consulta(f"página: {t} -> {p.status or p.erro}")
        if p.status == 200 and p.html:
            inicial = p
            break
        if p.status in (403, 503) and re.search(r"Just a moment|cf-chl|challenge-platform|captcha", p.html, re.I):
            motivo = "site protegido contra acesso automatizado (não contornado)"
            break
        motivo = p.erro or f"HTTP {p.status}"
        if p.status:  # o servidor respondeu: não adianta tentar variações de host
            break
    if not inicial:
        return paginas, motivo

    achados, meta = de_html(inicial.html, inicial.url_final)
    if len(meta.get("texto", "")) < 300:  # provavelmente renderizado por JavaScript
        lp = web.baixar_via_leitor(inicial.url_final)
        if lp:
            r.consulta(f"página (via leitor): {inicial.url_final}")
            achados.juntar(de_texto(lp.html))
            meta["texto"] = lp.html
    paginas.append((inicial.url_final, achados, meta))

    vistos = {inicial.url_final.rstrip("/"), site.rstrip("/")}
    candidatos = []
    for link, texto in meta.get("links_internos", []):
        if link.rstrip("/") in vistos or re.search(r"\.(pdf|jpe?g|png|zip|webp)$", link, re.I):
            continue
        if _RE_PAGINA_UTIL.search(link) or _RE_PAGINA_UTIL.search(texto or ""):
            vistos.add(link.rstrip("/"))
            candidatos.append(link)
    # Contato primeiro; depois institucional, políticas (costumam trazer CNPJ) e lojas/unidades.
    ordem = [r"contat|contact|fale|atendimento", r"sobre|quem.?somos|institucional|a-empresa",
             r"privacidade|privacy|termos|politica|pol%C3%ADtica", r"lojas|unidades|onde|localiza|endere"]
    candidatos.sort(key=lambda u: next((i for i, p in enumerate(ordem) if re.search(p, u, re.I)), len(ordem)))
    for link in candidatos[: config.MAX_PAGINAS_SITE - 1]:
        p = web.baixar(link)
        r.consulta(f"página: {link} -> {p.status or p.erro}")
        if p.status == 200 and p.html:
            a, m = de_html(p.html, p.url_final)
            paginas.append((p.url_final, a, m))
    return paginas, ""


def _site_confirma(nome: str, handle: str, site: str, paginas) -> bool:
    if not paginas:
        return False
    url, achados, meta = paginas[0]
    if handle and any(handle == urlparse(i).path.strip("/").lower() for _, a, _ in paginas for i in a.instagram):
        return True
    if not nome:
        return True
    if _pontuar_site(nome, site, meta.get("titulo", "")) >= 80:
        return True
    if similaridade(nome, meta.get("site_name", "")) >= 80:
        return True
    texto = normalizar(meta.get("titulo", "") + " " + meta.get("texto", "")[:20000])
    tokens = [t for t in normalizar(nome).split() if len(t) > 2]
    return bool(tokens) and normalizar(nome) in texto


def _cita_cidade(cidade: str, paginas) -> bool:
    alvo = normalizar(cidade)
    texto = " ".join(normalizar(m.get("titulo", "") + " " + m.get("texto", "")) for _, _, m in paginas)
    return bool(alvo) and f" {alvo} " in f" {texto} "


def _marca_no_site(nome: str, paginas) -> bool:
    """O site publica um CNPJ cujo nome é praticamente o procurado (site da rede/marca, sede em outra cidade)."""
    for c in unicos([c for _, a, _ in paginas for c in a.cnpjs])[:3]:
        try:
            cad = cadastro.consultar(c)
        except cadastro.CnpjInexistente:
            continue
        if cad and max(similaridade(nome, cad["nome_fantasia"]), similaridade(nome, cad["razao_social"])) >= 90:
            return True
    return False


def _instagrams_do_site(paginas) -> set[str]:
    return {urlparse(i).path.strip("/").lower() for _, a, _ in paginas for i in a.instagram}


def _homonimo_em_outra_cidade(nome: str, cidade: str, paginas) -> str:
    """Se o site não cita a cidade informada e as evidências dele apontam outra cidade, retorna essa cidade.

    Evidências: endereço no JSON-LD, cidade dos CEPs publicados e cidade do(s) CNPJ(s) publicados no site.
    Se o CNPJ do site tiver nome praticamente igual ao procurado (ex.: rede com sede em outra cidade), não
    considera homônimo.
    """
    alvo = normalizar(cidade)
    if alvo and _cita_cidade(cidade, paginas):
        return ""
    outras = []
    for _, a, _ in paginas:
        for org in a.jsonld:
            end = endereco_jsonld(org) or {}
            if end.get("cidade") and normalizar(end["cidade"]) != alvo:
                outras.append(end["cidade"])
    for cep in unicos([c for _, a, _ in paginas for c in a.ceps])[:2]:
        info = cadastro.consultar_cep(cep)
        if info and info["cidade"]:
            if normalizar(info["cidade"]) == alvo:
                return ""  # um CEP do site fica na cidade informada
            outras.append(f"{info['cidade']}/{info['uf']} (CEP {cep})")
    for c in unicos([c for _, a, _ in paginas for c in a.cnpjs])[:3]:
        try:
            cad = cadastro.consultar(c)
        except cadastro.CnpjInexistente:
            continue
        if not cad:
            continue
        if max(similaridade(nome, cad["nome_fantasia"]), similaridade(nome, cad["razao_social"])) >= 90:
            return ""  # mesma marca: provavelmente rede/filial, não homônimo
        if normalizar(cad["municipio"]) != alvo:
            outras.append(f"{cad['municipio']}/{cad['uf']}")
    return outras[0] if outras else ""


_NOMES_GENERICOS = {
    "home", "inicio", "pagina inicial", "homepage", "home page", "index", "bem vindo", "bem vindos", "welcome",
    "loja", "loja online", "loja virtual", "site oficial", "site", "principal", "default", "untitled", "wordpress",
}


def _nome_do_site(paginas) -> str:
    """Nome da empresa segundo o site: JSON-LD > og:site_name > título; nunca "Home"/"Início" etc."""
    url, achados, meta = paginas[0]
    titulo = meta.get("titulo", "")
    opcoes = [html.unescape(o["name"]).strip() for o in achados.jsonld if isinstance(o.get("name"), str)]
    opcoes += [meta.get("site_name", "")]
    opcoes += [p.strip() for p in re.split(r"\s+[|\-–—:]\s+", titulo)] if titulo else []
    rotulo = rotulo_dominio(url)
    validas = [o for o in opcoes if o and len(o) >= 3 and normalizar(o) not in _NOMES_GENERICOS]
    # Prefere a opção curta e parecida com o domínio (ex.: "Kopenhagen" em kopenhagen.com.br).
    parecidas = sorted((o for o in validas if compacto(o) and (
        compacto(o) in rotulo or rotulo in compacto(o) or fuzz.ratio(compacto(o), rotulo) >= 80)), key=len)
    if parecidas:
        # Título descritivo ("Chocolates, Doces Finos... Loja Kopenhagen"): o domínio é um nome melhor.
        return parecidas[0] if len(parecidas[0].split()) <= 4 else rotulo.capitalize()
    return validas[0] if validas and len(validas[0].split()) <= 6 else rotulo.capitalize()


def _registrar_achados_site(r: Registro, paginas, dom_site: str, handle: str, nome: str, confirmado: bool = True):
    """Grava o que o site traz. Com confirmado=False (site sem prova de ser desta empresa) tudo fica marcado."""

    def add(campo, valor, url):
        r.add(campo, valor, url, "site", confirmado)

    for url, a, meta in paginas[:1]:
        r.textos.append(f"{meta.get('titulo', '')} {meta.get('descricao', '')}")
    for url, a, _ in paginas:
        for h in a.horarios[:1]:
            add("horario_funcionamento", h, url)
        for av in a.avaliacoes[:1]:
            add("avaliacao", av, url)
        for org in a.jsonld:
            if cat := categorias.de_schema(org.get("@type")):
                add("categoria", categorias.rotulo(cat), url)
        for f in a.telefones:
            add("telefones", f, url)
        for f in a.whatsapp:
            add("whatsapp", f, url)
        # E-mails do próprio domínio primeiro.
        for e in sorted(a.emails, key=lambda e: 0 if dom_site and e.endswith("@" + dom_site) else 1):
            add("emails", e, url)
        # Sites costumam linkar perfis de parceiros/outras marcas: fica o mais parecido com o nome.
        def mais_parecido(urls):
            return sorted(urls, key=lambda u: -similaridade(nome, urlparse(u).path.strip("/").split("/")[-1]))[:1]

        if not handle:
            for i in mais_parecido(a.instagram):
                add("instagram", i, url)
        for f in mais_parecido(a.facebook):
            add("facebook", f, url)
        for li in mais_parecido(a.linkedin):
            add("linkedin", li, url)
        for o in a.outros[:4]:
            add("outros_canais", o, url)
        for org in a.jsonld:
            end = endereco_jsonld(org)
            if end:
                for k, campo in (("endereco", "endereco"), ("cidade", "cidade"), ("uf", "uf"), ("cep", "cep")):
                    add(campo, end.get(k), url)
        if not any(org.get("address") for org in a.jsonld):
            for end in a.enderecos[:1]:
                add("endereco", end, url)
            for cep in a.ceps[:1]:
                add("cep", cep, url)


# ------------------------------------------------------------------------------------------------- CNPJ

_DOMINIOS_GENERICOS = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "yahoo.com.br", "uol.com.br",
                        "bol.com.br", "terra.com.br", "ig.com.br", "live.com", "icloud.com", "globo.com"}


def _rua(endereco: str) -> str:
    """'Rua Haddock Lobo, 354 - Jardins' -> 'haddock lobo'"""
    t = normalizar(endereco.split(",")[0])
    t = re.sub(r"^(rua|r|avenida|av|alameda|al|rodovia|rod|travessa|tv|praca|estrada|largo)\s+", "", t)
    return re.sub(r"\s+\d+.*$", "", t).strip()


def _pontuar_candidato(cad: dict, nome: str, cidade: str, uf: str, dom_site: str, fones: set, origens: set,
                       dominios_email: set | None = None, enderecos: list | None = None):
    sim = max(similaridade(nome, cad["nome_fantasia"]), similaridade(nome, cad["razao_social"])) if nome else 0
    pts, motivos = sim * 0.5, [f"nome {sim:.0f}%"]
    if origens & {"site", "instagram", "entrada"}:
        pts += 45
        motivos.append("CNPJ publicado no site/perfil da empresa")
    elif nome and contido_com_extras(nome, cad["nome_fantasia"] or cad["razao_social"]):
        pts -= 10
        motivos.append("nome do cadastro = marca + termos extras (possível unidade franqueada)")
    dom_email = cad.get("email", "").rpartition("@")[2]
    if dom_email and dom_email not in _DOMINIOS_GENERICOS and (dom_email == dom_site or dom_email in (dominios_email or set())):
        pts += 20
        motivos.append("e-mail do cadastro usa o domínio do site/e-mails da empresa")
    if fones and set(cad.get("telefones", [])) & fones:
        pts += 15
        motivos.append("telefone do cadastro aparece no site/perfil")
    rua_cad = _rua(cad.get("endereco", ""))
    if rua_cad and len(rua_cad) > 3 and any(_rua(e) == rua_cad for e in enderecos or []):
        pts += 15
        motivos.append("endereço do site na mesma rua do cadastro")
    if cidade:
        if normalizar(cidade) == normalizar(cad["municipio"]):
            pts += 15
            motivos.append("mesma cidade")
        else:
            pts -= 20
            motivos.append(f"cidade diferente ({cad['municipio']}/{cad['uf']})")
    elif uf:
        pts += 5 if uf == cad["uf"] else -15
        motivos.append("mesma UF" if uf == cad["uf"] else f"UF diferente ({cad['uf']})")
    if cad["situacao"] and cad["situacao"] != "ATIVA":
        pts -= 10
        motivos.append(f"situação {cad['situacao']}")
    return round(pts, 1), sim, motivos


def aplicar_cadastro(r: Registro, cad: dict, origem: str = "cadastro", confirmado: bool = True):
    """Grava os dados da Receita. Com confirmado=False (CNPJ só provável) tudo fica marcado como não confirmado."""
    fonte = cad.get("fonte_url", "")
    c = confirmado
    r.add("cnpj", cnpjlib.formatar(cad["cnpj"]), fonte, origem, c)
    r.add("razao_social", cad["razao_social"], fonte, origem, c)
    if cad["nome_fantasia"]:
        r.add("nome_comercial", cad["nome_fantasia"].title(), fonte, "cadastro", c)
    r.add("situacao_cadastral", cad["situacao"], fonte, origem, c)
    r.add("data_situacao", cad["data_situacao"], fonte, origem, c)
    r.add("atividade_principal", cad["cnae"], fonte, origem, c)
    r.add("categoria", categorias.rotulo(categorias.de_cnae(cad["cnae"])), fonte, "cadastro", c)
    r.add("natureza_juridica", cad["natureza_juridica"], fonte, origem, c)
    r.add("porte", cad["porte"], fonte, origem, c)
    r.add("matriz_filial", cad["matriz_filial"], fonte, origem, c)
    r.add("endereco", cad["endereco"], fonte, "cadastro", c)
    r.add("bairro", cad["bairro"], fonte, "cadastro", c)
    r.add("cidade", cad["municipio"], fonte, "cadastro", c)
    r.add("uf", cad["uf"], fonte, "cadastro", c)
    if cad["cep"]:
        cep = re.sub(r"\D", "", cad["cep"])
        r.add("cep", f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cad["cep"], fonte, "cadastro", c)
    for f in cad["telefones"]:
        r.add("telefone_cadastro", f, fonte, "cadastro", c)
    if cad["email"]:
        r.add("email_cadastro", cad["email"], fonte, "cadastro", c)
    if cad["situacao"] and cad["situacao"] != "ATIVA":
        r.divergencia(f"Situação cadastral na Receita: {cad['situacao']} (desde {cad['data_situacao']})")
    if cad.get("mei") or "individual" in (cad.get("natureza_juridica") or "").lower():
        r.obs("Empresa individual/MEI: telefone e e-mail do cadastro podem ser pessoais — use com cuidado (LGPD).")


def _resolver_cnpj(r: Registro, nome: str, cidade: str, uf: str, dom_site: str, candidatos: dict):
    """candidatos: {cnpj: {"origens": set, "fontes": list}}"""
    # Só dados confirmados servem de evidência (um perfil não confirmado não pode confirmar um CNPJ).
    fones = set(r.valores("telefones", True)) | set(r.valores("whatsapp", True))
    dominios_email = {e.rpartition("@")[2] for e in r.valores("emails", True)}
    enderecos_site = [i["valor"] for i in r.entradas("endereco", True) if i["origem"] in ("site", "instagram", "revisao")]
    fortes = [c for c, v in candidatos.items() if v["origens"] & {"site", "instagram"}]
    fracos = [c for c in candidatos if c not in fortes]
    avaliados = []
    for c in (fortes + fracos)[:8]:
        try:
            cad = cadastro.consultar(c)
        except cadastro.CnpjInexistente:
            continue
        if not cad:
            r.obs(f"Não foi possível consultar o CNPJ {cnpjlib.formatar(c)} (bases indisponíveis)")
            continue
        pts, sim, motivos = _pontuar_candidato(cad, nome, cidade, uf, dom_site, fones, candidatos[c]["origens"],
                                               dominios_email, enderecos_site)
        avaliados.append((pts, sim, cad, motivos, candidatos[c]))

    def raiz(a):
        return cnpjlib.limpar(a[2]["cnpj"])[:8]

    # Uma única empresa (raiz) publicada no site/perfil oficial é forte evidência, mesmo com razão social
    # diferente da marca (ex.: Bob's -> CFK Comércio de Alimentos).
    raizes_fortes = {raiz(a) for a in avaliados if a[4]["origens"] & {"site", "instagram"}}
    if len(raizes_fortes) == 1:
        avaliados = [(p + 10, s, c, m + ["único CNPJ publicado no site/perfil"], i) if i["origens"] & {"site", "instagram"}
                     else (p, s, c, m, i) for p, s, c, m, i in avaliados]
    # Empate: matriz primeiro, depois CNPJ ativo.
    avaliados.sort(key=lambda x: (-x[0], not cnpjlib.e_matriz(x[2]["cnpj"]), x[2]["situacao"] != "ATIVA"))

    r.d["candidatos_cnpj"] = [
        {
            "cnpj": cnpjlib.formatar(cad["cnpj"]), "razao_social": cad["razao_social"],
            "nome_fantasia": cad["nome_fantasia"], "cidade": f"{cad['municipio']}/{cad['uf']}",
            "situacao": cad["situacao"], "pontuacao": pts, "motivos": "; ".join(motivos),
            "encontrado_em": " ".join(v["fontes"][:2]),
        }
        for pts, sim, cad, motivos, v in avaliados[:6]
    ]
    if not avaliados:
        return
    melhor = avaliados[0]
    pts, sim, cad, motivos, info = melhor
    # Estabelecimentos com a mesma raiz (matriz e filiais) são a mesma empresa: não concorrem entre si.
    # Empresas baixadas também não concorrem com uma ativa (costumam ser razões sociais antigas).
    concorrentes = [a for a in avaliados[1:] if raiz(a) != raiz(melhor)
                    and not (cad["situacao"] == "ATIVA" and a[2]["situacao"] not in ("ATIVA", ""))]
    mesma_raiz = any(raiz(a) == raiz(melhor) for a in avaliados[1:])
    segundo = concorrentes[0][0] if concorrentes else -999
    evidencia_site = any(m.startswith(("CNPJ publicado", "e-mail do cadastro", "telefone do cadastro", "endereço do site"))
                         for m in motivos)
    # Com site conhecido, um CNPJ achado só pelo nome precisa ter nome compatível com o domínio do site.
    compativel_site = (not dom_site or evidencia_site
                       or max(fuzz.partial_ratio(rotulo_dominio(dom_site), compacto(cad["nome_fantasia"]) or "-"),
                              fuzz.partial_ratio(rotulo_dominio(dom_site), compacto(cad["razao_social"]) or "-")) >= 80)

    provavel = False
    if pts >= 60 and pts - segundo >= 15 and compativel_site:
        escolhido = True
    elif pts >= 45 and sim >= 85 and compativel_site and not any(a[1] >= 85 for a in concorrentes):
        escolhido = True
        r.obs("CNPJ escolhido só por correspondência de nome — confirmar.")
    else:
        escolhido = False
        # Sem confirmação: ainda assim traz o candidato mais plausível, marcado como NÃO confirmado.
        # Plausível = nome parecido ou CNPJ publicado no site/perfil; nome sem relação nenhuma não entra.
        elegiveis = [a for a in avaliados if a[1] >= 70 or any(m.startswith("CNPJ publicado") for m in a[3])]
        # Empresa ativa antes de baixada/inapta (um CNPJ fechado há décadas não serve para prospecção).
        elegiveis.sort(key=lambda a: (a[2]["situacao"] != "ATIVA", -a[0]))
        if elegiveis:
            provavel = True
            melhor = elegiveis[0]
            pts, sim, cad, motivos, info = melhor
            concorrentes = [a for a in avaliados if raiz(a) != raiz(melhor)
                            and not (cad["situacao"] == "ATIVA" and a[2]["situacao"] not in ("ATIVA", ""))]
            mesma_raiz = any(raiz(a) == raiz(melhor) for a in avaliados if a is not melhor)
            duvidas = []
            proximo = next((a for a in concorrentes if a[0] >= pts - 15), None)
            if proximo:
                duvidas.append(f"pontuação próxima de {cnpjlib.formatar(proximo[2]['cnpj'])} ({proximo[2]['razao_social']}, "
                               f"{proximo[2]['municipio']}/{proximo[2]['uf']})")
            if any("cidade diferente" in m or "UF diferente" in m for m in motivos):
                duvidas.append(f"fica em {cad['municipio']}/{cad['uf']}, não na cidade informada")
            if not compativel_site:
                duvidas.append("razão social/nome fantasia não combinam com o domínio do site")
            seg_nome, seg_cnpj = categorias.por_palavras(nome), categorias.de_cnae(cad["cnae"])
            if seg_nome and seg_cnpj and seg_nome != seg_cnpj:
                duvidas.append(f"a atividade do CNPJ ({categorias.rotulo(seg_cnpj)}) não parece de "
                               f"{categorias.rotulo(seg_nome).lower()}")
            if not any(m.startswith(("CNPJ publicado", "e-mail do cadastro", "telefone do cadastro", "endereço do site"))
                       for m in motivos):
                duvidas.append("encontrado só por nome em resultados de busca")
            r.obs("CNPJ PROVÁVEL, NÃO CONFIRMADO" + (f" ({'; '.join(duvidas)})" if duvidas else "")
                  + ". Outros candidatos na aba Alternativas.")

    if (escolhido or provavel) and mesma_raiz:
        mesma = [a for a in avaliados if raiz(a) == raiz(melhor)]
        # Endereço ou telefone do site identifica a unidade só se bater com UM estabelecimento ativo
        # (telefone/e-mail do cadastro costumam ser os mesmos em todas as filiais) e o site citar uma única rua.
        def com(prefixo):
            return [a for a in mesma if a[2]["situacao"] == "ATIVA" and any(m.startswith(prefixo) for m in a[3])]
        por_endereco, por_fone = com("endereço do site"), com("telefone do cadastro")
        ruas_site = {_rua(e) for e in enderecos_site if _rua(e)}
        unidade = (por_endereco[0] if len(por_endereco) == 1 and len(ruas_site) == 1
                   else por_fone[0] if len(por_fone) == 1 else None)
        matriz = next((a for a in mesma if cnpjlib.e_matriz(a[2]["cnpj"]) and a[2]["situacao"] == "ATIVA" and a[0] >= pts - 20), None)
        if unidade:
            pts, sim, cad, motivos, info = unidade
            if not cnpjlib.e_matriz(cad["cnpj"]):
                r.obs("Rede com vários estabelecimentos: escolhida a unidade cujo endereço/telefone aparece no site.")
        elif matriz and not cnpjlib.e_matriz(cad["cnpj"]):
            pts, sim, cad, motivos, info = matriz
            r.obs("Rede com vários estabelecimentos e sem pista da unidade: escolhida a matriz.")

    homonimas = [a for a in concorrentes if a[1] >= 85 and a[2]["situacao"] == "ATIVA"]
    if escolhido and len(homonimas) >= 2:
        r.d["teto_confianca"] = "media"
        r.obs(f"Há {len(homonimas)} outras empresas ativas com nome igual/parecido (franquias, licenciados ou "
              "homônimas) — confira se a entidade escolhida é a desejada.")

    if escolhido or provavel:
        r.d["pontuacao_cnpj"] = pts
        for f in info["fontes"][:2]:
            r.add("cnpj", cnpjlib.formatar(cad["cnpj"]), f, sorted(info["origens"], key=lambda o: _PRIORIDADE.get(o, 9))[0],
                  confirmado=escolhido)
        aplicar_cadastro(r, cad, confirmado=escolhido)
        if cad["situacao"] != "ATIVA" and not cnpjlib.e_matriz(cad["cnpj"]):
            try:
                m = cadastro.consultar(cnpjlib.matriz_de(cad["cnpj"]))
            except cadastro.CnpjInexistente:
                m = None
            if m:
                r.obs(f"O CNPJ encontrado não está ativo; a matriz da mesma raiz, {cnpjlib.formatar(m['cnpj'])} "
                      f"({m['razao_social']}, {m['municipio']}/{m['uf']}), está {m['situacao']}. Fonte: {m['fonte_url']}")
        if mesma_raiz:
            outros = [cnpjlib.formatar(a[2]["cnpj"]) for a in avaliados if a[2]["cnpj"] != cad["cnpj"]
                      and cnpjlib.limpar(a[2]["cnpj"])[:8] == cnpjlib.limpar(cad["cnpj"])[:8]]
            r.obs(f"Outros estabelecimentos da mesma empresa encontrados: {', '.join(outros)}")
        marca = "sim" if escolhido else "provável (não confirmado)"
        if not any(c["cnpj"] == cnpjlib.formatar(cad["cnpj"]) for c in r.d["candidatos_cnpj"]):
            r.d["candidatos_cnpj"].insert(0, {
                "cnpj": cnpjlib.formatar(cad["cnpj"]), "razao_social": cad["razao_social"],
                "nome_fantasia": cad["nome_fantasia"], "cidade": f"{cad['municipio']}/{cad['uf']}",
                "situacao": cad["situacao"], "pontuacao": pts, "motivos": "; ".join(motivos),
                "encontrado_em": " ".join(info["fontes"][:2])})
        for c in r.d["candidatos_cnpj"]:
            c["escolhido"] = marca if c["cnpj"] == cnpjlib.formatar(cad["cnpj"]) else ""
    elif avaliados:
        r.obs("Nenhum CNPJ candidato tem nome parecido com o da empresa; candidatos na aba Alternativas.")


# --------------------------------------------------------------------------------------- orquestração

def _pesquisar(e: Entrada, r: Registro):
    nome, cidade, uf, handle, site = e.nome, e.cidade, e.uf, e.instagram, e.site
    cad = None
    candidatos: dict[str, dict] = {}

    def candidato(c, origem, fonte):
        v = candidatos.setdefault(cnpjlib.limpar(c), {"origens": set(), "fontes": []})
        v["origens"].add(origem)
        if fonte not in v["fontes"]:
            v["fontes"].append(fonte)

    if nome:
        r.add("nome_comercial", nome, "", "entrada")

    # 1. CNPJ informado
    if e.cnpj:
        try:
            cad = cadastro.consultar(e.cnpj)
        except cadastro.CnpjInexistente as x:
            r.divergencia(str(x))
        if cad:
            aplicar_cadastro(r, cad, origem="cadastro")
            r.d["pontuacao_cnpj"] = 100
            nome = nome or cad["nome_fantasia"] or cad["razao_social"]
            cidade, uf = cidade or cad["municipio"], uf or cad["uf"]
        elif not r.d["divergencias"]:
            r.obs("Bases públicas de CNPJ não responderam; tente novamente mais tarde.")

    # 2. Instagram informado
    sugeridos = []
    if handle:
        url_ig = f"https://www.instagram.com/{handle}/"
        r.add("instagram", url_ig, url_ig, "entrada")
        perfil = perfil_instagram(handle)
        r.consulta(f"perfil: {url_ig} -> {perfil['erro'] or 'ok'}")
        if perfil["nome"]:
            r.add("nome_comercial", perfil["nome"], url_ig, "instagram")
            nome = nome or perfil["nome"]
        if (n := seguidores_em(perfil.get("resumo"))) is not None:
            r.add("seguidores_instagram", str(n), url_ig, "instagram")
        elif perfil["erro"] and "404" in perfil["erro"]:
            r.divergencia("Perfil do Instagram não encontrado (HTTP 404).")
        achados_ig, sugeridos = _trechos_instagram(r, handle)
        for c in achados_ig.cnpjs:
            candidato(c, "instagram", url_ig)
        # Perfil sem nome público: o "nome" é só o @, evidência fraca para achar o site certo.
        nome_so_do_handle = not (nome or r.valor("nome_comercial"))
        nome = nome or r.valor("nome_comercial") or handle
    else:
        nome_so_do_handle = False

    # 3. Site
    if site:
        r.add("site", site, site, "entrada")
    elif nome:
        site, _ = descobrir_site(r, nome, cidade, uf, sugeridos)

    paginas = []
    if site:
        paginas, motivo = ler_site(r, site)
        site_confirmado = True
        if not paginas:
            r.obs(f"Site {site} não pôde ser lido: {motivo}.")
            # Sem conteúdo para confirmar: um site descoberto só é confirmado se o domínio for praticamente o nome;
            # senão entra como não confirmado.
            site_confirmado = bool(e.site) or _pontuar_dominio(nome, site) >= 88
        elif not e.site and not _site_confirma(nome, handle, site, paginas):
            r.alternativa("site", site, "rejeitado: o site não menciona a empresa", site)
            r.obs(f"Site candidato {site} descartado: não menciona a empresa (aba Alternativas).")
            site, paginas = "", []
        elif not e.site and e.cidade and (homonimo := _homonimo_em_outra_cidade(nome, e.cidade, paginas)):
            r.alternativa("site", site, f"rejeitado: parece ser de empresa homônima em {homonimo}", paginas[0][0])
            r.obs(f"Site {site} descartado: parece ser de empresa homônima em {homonimo} "
                  f"(a cidade informada, {e.cidade}, não aparece no site; aba Alternativas).")
            site, paginas = "", []
        if paginas and not e.site:
            igs = _instagrams_do_site(paginas)
            if handle and handle in igs:
                pass  # o site linka o perfil informado: confirmado
            elif handle and igs:
                site_confirmado = False
                r.obs(f"Site {site} linka outro Instagram (@{', @'.join(sorted(igs)[:3])}), não @{handle}: "
                      "dados do site NÃO confirmados.")
            elif handle and nome_so_do_handle and fuzz.ratio(re.sub(r"[^a-z0-9]", "", handle), rotulo_dominio(site)) < 95:
                site_confirmado = False
                r.obs(f"Site {site} achado só pelo @{handle} (o perfil não tem nome público) e não linka o perfil: "
                      "dados do site NÃO confirmados.")
            elif e.cidade and not _cita_cidade(e.cidade, paginas) and not _marca_no_site(nome, paginas):
                site_confirmado = False
                r.obs(f"Site {site} não cita a cidade informada ({e.cidade}): pode ser homônima; "
                      "dados do site NÃO confirmados.")
        if site and not e.site:
            base = f"{urlparse(paginas[0][0]).scheme}://{urlparse(paginas[0][0]).netloc}/" if paginas else site
            r.add("site", base, paginas[0][0] if paginas else site, "busca", site_confirmado)
    if paginas:
        nome_site = _nome_do_site(paginas)
        if nome_site and not nome:
            nome = nome_site
        if nome_site:
            r.add("nome_comercial", nome_site, paginas[0][0], "site", site_confirmado)
        dom_site = dominio(paginas[0][0])
        _registrar_achados_site(r, paginas, dom_site, handle, nome, site_confirmado)
        for url, a, _ in paginas:
            for c in a.cnpjs:
                # CNPJ de um site não confirmado é só uma pista (não vale como "publicado no site oficial").
                candidato(c, "site" if site_confirmado else "busca", url)
    dom_site = dominio(r.valor("site", True)) if r.valor("site", True) else ""

    # 4. Instagram descoberto pelo site/busca: buscar trechos do perfil também (dados herdam a confirmação do perfil)
    if not handle and r.valor("instagram"):
        handle_achado = urlparse(r.valor("instagram")).path.strip("/").lower()
        if handle_achado:
            ig_confirmado = r.confirmado("instagram")
            achados_ig, _ = _trechos_instagram(r, handle_achado, ig_confirmado)
            for c in achados_ig.cnpjs:
                candidato(c, "instagram" if ig_confirmado else "busca", r.valor("instagram"))

    if not nome:
        r.d["status"] = "nao_encontrada"
        return

    # 5. CNPJ
    if not cad:
        if not any(v["origens"] & {"site", "instagram"} for v in candidatos.values()):
            consultas = [" ".join(x for x in (nome, "CNPJ", cidade, uf) if x)]
            if dom_site:
                consultas.append(f'"{dom_site}" CNPJ')
            for q in consultas:
                r.consulta(f"busca: {q}")
                for x in web.buscar(q, 10):
                    for c in cnpjlib.encontrar(f"{x.url} {x.titulo} {x.trecho}"):
                        candidato(c, "busca", x.url)
        if candidatos:
            _resolver_cnpj(r, nome, cidade, uf, dom_site, candidatos)

    # 6. CEP sem cadastro: completa rua/bairro/cidade/UF pela consulta pública de CEP
    if r.valor("cep") and not (r.valor("cidade") and r.valor("bairro")):
        cep_conf = r.confirmado("cep")
        info = cadastro.consultar_cep(r.valor("cep"))
        r.consulta(f"cep: {r.valor('cep')} -> {'ok' if info else 'não encontrado'}")
        if info:
            for campo, chave in (("endereco", "logradouro"), ("bairro", "bairro"), ("cidade", "cidade"), ("uf", "uf")):
                if not r.valor(campo):
                    r.add(campo, info[chave], info["fonte_url"], "cep", cep_conf)
        else:
            r.obs(f"CEP {r.valor('cep')} não encontrado nas bases públicas de CEP.")

    # 7. Coerência com as pistas
    cid_cad = r.valor("cidade")
    if e.cidade and cid_cad and normalizar(e.cidade) != normalizar(cid_cad):
        r.divergencia(f"Cidade informada ({e.cidade}) difere da cidade do cadastro/site ({cid_cad}) — pode ser filial/unidade.")
    if e.uf and r.valor("uf") and e.uf != sigla_uf(r.valor("uf")):
        r.divergencia(f"UF informada ({e.uf}) difere da encontrada ({r.valor('uf')}).")
    ceps_site = {i["valor"] for i in r.entradas("cep") if i["origem"] == "site"}
    ceps_cad = {i["valor"] for i in r.entradas("cep") if i["origem"] == "cadastro"}
    if ceps_site and ceps_cad and not ceps_site & ceps_cad:
        r.obs(f"CEP no site ({', '.join(ceps_site)}) difere do cadastro ({', '.join(ceps_cad)}) — pode ser outra unidade.")

    # 8. Google Maps (link de busca montado com nome + endereço; confirmado se o endereço for)
    end = ", ".join(x for x in (r.valor("endereco"), r.valor("bairro"), r.valor("cidade"), r.valor("uf"), r.valor("cep")) if x)
    if end:
        consulta = f"{r.valor('nome_comercial') or nome}, {end}"
        r.add("google_maps", f"https://www.google.com/maps/search/?api=1&query={quote(consulta)}", "", "gerado",
              r.confirmado("endereco") or r.confirmado("cep"))

    # 9. Segmento (A–M): o CNAE e o tipo do site já entraram acima. Sem nenhum dos dois, tenta inferir pelo
    #    nome/site, com as mesmas regras A–M dos perfis; a inferência fica marcada como NÃO confirmada.
    #    Empresa fora dos 13 segmentos fica sem segmento — é o esperado, não uma falha.
    if not r.valor("categoria"):
        texto = " ".join([nome, r.valor("nome_comercial")] + r.textos + [r.valor("razao_social")])
        if seg := categorias.por_palavras(texto):
            r.add("categoria", categorias.rotulo(seg), "", "gerado", confirmado=False)


def campos_nao_confirmados(r: Registro) -> list[str]:
    """Campos cuja célula na planilha mostra algum valor não confirmado."""
    saida = []
    for c in CAMPOS:
        itens = r.entradas(c)  # confirmados primeiro
        if not itens:
            continue
        if c in CAMPOS_MULTIPLOS:
            # Um item por valor (o mesmo valor pode ter vindo de uma fonte confirmada e de outra não).
            vistos, mostrados = set(), []
            for i in itens:
                if (k := normalizar(i["valor"])) not in vistos:
                    vistos.add(k)
                    mostrados.append(i)
        else:
            mostrados = itens[:1]
        if any(not i.get("confirmado", True) for i in mostrados):
            saida.append(c)
    return saida


def _finalizar(r: Registro, e: Entrada | None = None):
    d = r.d
    presenca = ("site", "instagram", "telefones", "whatsapp", "emails")
    if d["status"] == "erro":
        d["confianca"] = "baixa"
    elif r.valor("cnpj", True):
        d["status"] = "identificada"
        pts = d["pontuacao_cnpj"] or 0
        d["confianca"] = "alta" if pts >= 80 else "media" if pts >= 60 else "baixa"
        if (d["divergencias"] or d.get("teto_confianca") == "media") and d["confianca"] == "alta":
            d["confianca"] = "media"
    elif r.valor("cnpj"):
        d["status"] = "provavel"  # CNPJ mais plausível preenchido, mas NÃO confirmado
        d["confianca"] = "baixa"
    elif any(r.valor(c) for c in presenca):
        d["status"] = "parcial"
        d["confianca"] = "media" if any(r.valor(c, True) for c in presenca) else "baixa"
    else:
        d["status"] = "nao_encontrada"
        d["confianca"] = "baixa"
    d["nao_encontrados"] = [c for c in CAMPOS_ESSENCIAIS if not r.valor(c)]
    d["nao_confirmados"] = campos_nao_confirmados(r)
    # Divergência entre valores de campos únicos vindos de fontes diferentes
    for campo in ("cidade", "uf", "cnpj"):
        vals = r.valores(campo)
        if len(vals) > 1:
            r.divergencia(f"{campo}: valores diferentes encontrados ({' / '.join(vals)})")


def pesquisar(e: Entrada) -> dict:
    r = Registro(e)
    try:
        _pesquisar(e, r)
    except Exception as x:  # uma empresa com erro não interrompe o lote
        r.d["status"] = "erro"
        r.obs(f"Erro: {type(x).__name__}: {x}")
        r.d["erro_detalhe"] = traceback.format_exc()[-2000:]
    _finalizar(r, e)
    return r.d
